import re
from lxml import etree
import sys
import click
from stiff.utils import parse_qs_single, wnlemma_to_analy_lemma
from stiff.utils.xml import (
    eq_matcher,
    iter_sentences,
    transform_sentences,
    transform_blocks,
    BYPASS,
    chunk_cb,
    write_event,
    fixup_missing_text,
    iter_sentences_opensubs18,
)
from xml.sax.saxutils import escape
import pygtrie
from stiff.data.constants import WN_UNI_POS_MAP, UNI_POS_WN_MAP
from finntk.wordnet.reader import fiwn, get_en_fi_maps
from finntk.wordnet.utils import pre_id_to_post, post_id_to_pre, pre2ss
from finntk.omor.extract import lemma_intersect
from os.path import join as pjoin
from os import makedirs, listdir
from contextlib import contextmanager
from typing import Dict, Set, IO
from collections import Counter
from urllib.parse import urlencode
import pickle


@click.group("munge")
def munge():
    """
    Munge between different stream/corpus formats.
    """
    pass


def opensubs18_ids_to_unified(iter_stiff):
    imdb_counter = Counter()
    prev_imdb = None
    for (sources, imdb, sent_id), sent_elem in iter_stiff:
        if prev_imdb is not None and imdb != prev_imdb:
            imdb_counter[prev_imdb] += 1
        yield (
            "stiff.{:010d}.{:03d}.{:08d}".format(
                int(imdb), imdb_counter[imdb], int(sent_id)
            ),
            sent_elem,
        )


def iter_sentences_opensubs18_man_ann(stream):
    # XXX: This assumes a 1-1 imdb subtitle correspondance -- which should be
    # the case near the beginning where the man-ann takes place, but should be
    # fixed in general
    for sent in iter_sentences(stream):
        sources, imdb, sent_id = sent.attrib["id"].split("; ")
        sent_id = "stiff.{:010d}.000.{:08d}".format(int(imdb), int(sent_id))
        yield sent_id, sent


def iter_sentences_eurosense(stream):
    for sent_elem in iter_sentences(stream):
        yield "eurosense.{:08d}".format(int(sent_elem.attrib["id"])), sent_elem


def get_lemma(ann):
    best_lemma = None
    best_lemma_goodness = -2
    assert ann.attrib["wnlemma"]
    for idx, lemma_bit in enumerate(ann.attrib["wnlemma"].split(" ")):
        lemma_dict = parse_qs_single(lemma_bit)
        lemma = lemma_dict["l"]
        wn_lemma_surfed = wnlemma_to_analy_lemma(lemma)
        goodness = (
            2
            if wn_lemma_surfed == ann.attrib["lemma"]
            else (1 if wn_lemma_surfed == ann.attrib["anchor"].lower() else -idx)
        )
        if goodness > best_lemma_goodness:
            best_lemma = lemma
            best_lemma_goodness = goodness
    assert best_lemma is not None
    return best_lemma


@munge.command("stiff-to-unified")
@click.argument("stiff", type=click.File("rb"))
@click.argument("unified", type=click.File("w"))
@click.option(
    "--input-fmt",
    type=click.Choice(["man-ann-stiff", "man-ann-europarl", "stiff"]),
    default="stiff",
)
def stiff_to_unified(stiff: IO, unified: IO, input_fmt: str):
    """
    Do the XML conversion from the STIFF format (similar to the Eurosense
    format) to the Unified format. Note that this assumes is that previous
    filtering has produced an unambiguous tagging.
    """
    write_header(unified, "eurosense" if input_fmt == "man-ann-europarl" else "stiff")
    if input_fmt == "man-ann-stiff":
        sent_iter = iter_sentences_opensubs18_man_ann(stiff)
    elif input_fmt == "stiff":
        sent_iter = opensubs18_ids_to_unified(iter_sentences_opensubs18(stiff))
    else:
        assert input_fmt == "man-ann-europarl"
        sent_iter = iter_sentences_eurosense(stiff)
    for sent_id, sent_elem in sent_iter:
        unified.write('<sentence id="{}">\n'.format(sent_id))
        text_elem = sent_elem.xpath("text")[0]
        text_id = text_elem.attrib.get("id")
        anns = []
        for ann in sent_elem.xpath(".//annotation"):
            our_pos = None
            for pos_enc in ann.attrib["anchor-positions"].split(" "):
                pos = parse_qs_single(pos_enc)
                if text_id is None or pos["from-id"] == text_id:
                    our_pos = pos
            assert our_pos is not None, "Didn't find a usable anchor position"
            char_id = int(our_pos["char"])
            anns.append((char_id, ann.attrib["anchor"], get_lemma(ann), ann.text))
        anns.sort()
        sent = text_elem.text
        cursor = 0
        while cursor < len(sent):
            instance = None
            while 1:
                if not len(anns):
                    break
                char_id, anchor, lemma, ann = anns[0]
                assert (
                    char_id >= cursor
                ), "Moved past anchor position - can't have overlapping anchors"
                if char_id > cursor:
                    # Try again to move past leading punctation which has been
                    # put in the same token like: `-ajoneuvo` with anchor
                    # ajoneuvo

                    # XXX: This approach just deletes the leading punctation.
                    # Probably not what is wanted but servicable for the time
                    # being.
                    old_cursor = cursor
                    while not (
                        sent[cursor].isalnum() or sent[cursor].isspace()
                    ) and cursor < min(char_id, len(sent)):
                        cursor += 1
                    if cursor != char_id:
                        # Reset
                        cursor = old_cursor
                        break
                if instance is None:
                    instance = {"lemma": lemma, "anchor": anchor, "key": []}
                else:
                    assert (
                        instance["lemma"] == lemma
                    ), "Can't tag an instance with multiple lemmas"
                    assert (
                        instance["anchor"] == anchor
                    ), "Can't have different anchors at different positions"
                instance["key"].append(ann)
                del anns[0]
            if instance is not None:
                pos = WN_UNI_POS_MAP[instance["key"][-1][-1]]
                unified.write(
                    '<instance lemma="{}" key="{}" pos="{}">{}</instance>\n'.format(
                        instance["lemma"],
                        " ".join(instance["key"]),
                        pos,
                        instance["anchor"],
                    )
                )
                # XXX: This approach just deletes the trailing punctation.
                # Probably not what is wanted but servicable for the time
                # being. Old code:
                # cursor += len(instance["anchor"]) + 1

                end_pos = sent.find(" ", cursor)
                if end_pos == -1:
                    break
                cursor = end_pos + 1
            else:
                end_pos = sent.find(" ", cursor)
                if end_pos == -1:
                    end_pos = None
                unified.write("<wf>{}</wf>\n".format(escape(sent[cursor:end_pos])))
                if end_pos is None:
                    break
                cursor = end_pos + 1
        unified.write("</sentence>")

    unified.write("</text>\n")
    unified.write("</corpus>\n")


@munge.command("unified-split")
@click.argument("inf", type=click.File("rb", lazy=True))
@click.argument("outf", type=click.File("wb"))
@click.argument("keyout", type=click.File("w"))
def unified_split(inf: IO, outf: IO, keyout: IO):
    """
    Split a keyfile out of a variant of the unified format which includes sense
    keys inline.
    """

    def sent_split_key(sent_elem):
        sent_id = sent_elem.attrib["id"]
        for idx, inst in enumerate(sent_elem.xpath("instance")):
            key = inst.attrib["key"]
            del inst.attrib["key"]
            key_id = "{}.{:08d}".format(sent_id, idx)
            inst.attrib["id"] = key_id
            keyout.write("{} {}\n".format(key_id, key))

    transform_sentences(inf, sent_split_key, outf)


def iter_anchored_anns(sent_elem, once_only=True):
    anns = list(sent_elem.xpath(".//annotation"))
    sent = sent_elem.xpath("text")[0].text
    prev_anns_count = len(anns) + 1
    # The annotations are almost always in order, but very occasionally we need
    # to go back to the beginning of the sentence for more.
    while 0 < len(anns) < prev_anns_count:
        prev_anns_count = len(anns)
        cursor = 0
        tok_cursor = 0
        while anns:
            # print((anns[0].attrib["anchor"], sent[cursor:]) if anns else ("X", sent[cursor:]))
            match_pos = sent.find(anns[0].attrib["anchor"], cursor)
            if match_pos == -1:
                break
            tok_cursor += sent.count(" ", cursor, match_pos)
            ann = anns.pop(0)
            anchor = ann.attrib["anchor"]
            yield tok_cursor, match_pos, anchor, ann
            cursor = match_pos
        if once_only:
            break
    if once_only:
        if len(anns):
            sys.stderr.write(
                "Sentence {} has {} additional unused annotation\n".format(
                    sent_elem.attrib["id"], len(anns)
                )
            )
    else:
        assert len(anns) == 0


@munge.command("eurosense-add-anchor-positions")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def eurosense_add_anchor_positions(inf: IO, outf: IO):
    def add_anchor_positions(sent_elem):
        for tok_cursor, cursor, _match_anchor, ann in iter_anchored_anns(sent_elem):
            if ann is None:
                continue
            ann.attrib["anchor-positions"] = f"token={tok_cursor}&char={cursor}"

    transform_sentences(inf, add_anchor_positions, outf)


def write_header(unified, source):
    unified.write('<?xml version="1.0" encoding="UTF-8" ?>\n')
    unified.write('<corpus lang="fi" source="' + source + '">\n')
    unified.write('<text id="' + source + '">\n')


@munge.command("eurosense-to-unified")
@click.argument("eurosense", type=click.File("rb", lazy=True))
@click.argument("unified", type=click.File("w"))
def eurosense_to_unified(eurosense: IO, unified: IO):
    """
    Do the XML conversion from the Eurosense format to the Unified format. Note
    that this only deals with XML and doesn't convert other things like synset
    ids. For the full conversion pipeline see eurosense2unified in
    `pipeline.py`.
    """
    write_header(unified, "eurosense")
    for sent_id, sent_elem in iter_sentences_eurosense(eurosense):
        unified.write('<sentence id="{}">\n'.format(sent_id))
        trie = pygtrie.StringTrie(separator=" ")
        anns = sent_elem.xpath(".//annotation")
        for ann in anns:
            trie[ann.attrib["anchor"]] = (ann.text, ann.attrib["lemma"])
        sent = sent_elem.xpath("text")[0].text
        cursor = 0
        while cursor < len(sent):
            match_anchor, match_val = trie.longest_prefix(sent[cursor:])
            if match_anchor:
                sense_key, lemma = match_val
                pos = WN_UNI_POS_MAP[sense_key[-1]]
                unified.write(
                    '<instance lemma="{}" pos="{}" key="{}">{}</instance>\n'.format(
                        lemma, pos, sense_key, match_anchor
                    )
                )
                cursor += len(match_anchor) + 1
            else:
                end_pos = sent.find(" ", cursor)
                if end_pos == -1:
                    break
                unified.write("<wf>{}</wf>\n".format(escape(sent[cursor:end_pos])))
                cursor = end_pos + 1
        unified.write("</sentence>\n")
    unified.write("</text>\n")
    unified.write("</corpus>\n")


@munge.command("lemma-to-synset")
@click.argument("inf", type=click.File("rb", lazy=True))
@click.argument("outf", type=click.File("wb"))
def lemma_to_synset(inf: IO, outf: IO):
    from stiff.munge.utils import synset_id_of_ann

    def l2ss(ann):
        ann.text = pre_id_to_post(synset_id_of_ann(ann))

    transform_blocks(eq_matcher("annotation"), inf, l2ss, outf)


def iter_synsets(synset_list):
    fi2en, en2fi = get_en_fi_maps()
    for synset_id in synset_list.split(" "):
        fi_pre_synset = en2fi[post_id_to_pre(synset_id)]
        synset = pre2ss(fiwn, fi_pre_synset)
        yield synset_id, synset


@munge.command("eurosense-lemma-fix")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--keep-unknown/--drop-unknown")
@click.option("--quiet", default=False)
def eurosense_fix_lemmas(inf: IO, outf: IO, keep_unknown: bool, quiet: bool):
    """
    Eurosense contains many lemmas which are not in the set of lemmas for the
    synset in FinnWordNet. There are two reasons this might occur.

    Scenario A) Bad lemmatisation by Babelfy. In this case we can try and
    recover the correct lemma by lemmatising ourself and combining with
    information from WordNet

    Scenario B) Extra lemmas have been associated with the WordNet synset in
    BabelNet.  In this case there's nothing to do, and we should usually just
    drop the annotation.
    """
    fi2en, en2fi = get_en_fi_maps()

    def ann_fix_lemmas(ann):
        # 1) check if their lemmatisation matches something in FiWN as is
        orig_lemma_str = ann.attrib["lemma"]
        orig_lemma_str = orig_lemma_str.replace("#", "").replace(" ", "_")

        def mk_lemma_synset_map(lower=False):
            lemma_synset_map = {}
            for synset_id, synset in iter_synsets(ann.text):
                for lemma in synset.lemmas():
                    lemma_str = lemma.name()
                    if lower:
                        lemma_str = lemma_str.lower()
                    lemma_synset_map.setdefault(lemma_str, set()).add(synset_id)
            return lemma_synset_map

        lemma_synset_map = mk_lemma_synset_map()

        if orig_lemma_str in lemma_synset_map:
            ann.text = " ".join(lemma_synset_map[orig_lemma_str])
            ann.attrib["lemma"] = orig_lemma_str
            return
        # 2) Try and just use the surface as is as the lemma
        lemmatised_anchor = ann.attrib["anchor"].replace(" ", "_")

        lemma_synset_map_lower = mk_lemma_synset_map(lower=True)
        if lemmatised_anchor.lower() in lemma_synset_map_lower:
            ann.text = " ".join(lemma_synset_map_lower[lemmatised_anchor.lower()])
            # XXX: Should be lemma in original case rather than anchor in original case
            ann.attrib["lemma"] = lemmatised_anchor
            return
        # 3) Re-lemmatise the surface using OMorFi and try and match with FiWN
        anchor_bits = ann.attrib["anchor"].split(" ")
        matches = {}

        for lemma_str, synset_id in lemma_synset_map.items():
            lemma_bits = lemma_str.split("_")
            common = lemma_intersect(anchor_bits, lemma_bits)
            if common is not None:
                matches.setdefault(lemma_str, set()).update(synset_id)
        if len(matches) == 1:
            lemma, synsets = next(iter(matches.items()))
            ann.attrib["lemma"] = lemma
            ann.text = " ".join(synsets)
            return
        elif len(matches) > 1:
            if not quiet:
                sys.stderr.write(
                    "Multiple lemmas found found for {}: {}\n".format(
                        ann.attrib["anchor"], matches
                    )
                )
        # If nothing has worked, it's probably scenario B as above
        elif len(matches) == 0:
            if not quiet:
                sys.stderr.write(
                    "No lemma found for {} {} {}\n".format(
                        ann.text, orig_lemma_str, lemmatised_anchor
                    )
                )
        if keep_unknown:
            ann.attrib["lemma"] = orig_lemma_str
        else:
            return BYPASS

    transform_blocks(eq_matcher("annotation"), inf, ann_fix_lemmas, outf)


@munge.command("eurosense-reanchor")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def eurosense_reanchor(inf: IO, outf: IO):
    """
    Reanchors Eurosense lemmas which are actually forms including some "light"
    word like ei and olla by removing said unneccesary word.
    """
    EXTRA_BITS = {"ei", "olla"}
    fi2en, en2fi = get_en_fi_maps()

    def ann_reanchor(ann):
        all_lemma_names = []
        for _, synset in iter_synsets(ann.text):
            for lemma in synset.lemmas():
                all_lemma_names.append(lemma.name())
        if " " not in ann.attrib["lemma"]:
            return
        lem_begin, lem_rest = ann.attrib["lemma"].split(" ", 1)
        if lem_begin not in EXTRA_BITS:
            return
        anchor_begin = ann.attrib["anchor"].split(" ", 1)[0]
        for lemma_name in all_lemma_names:
            if lemma_name.split("_", 1)[0] in (anchor_begin, lem_begin):
                return
        ann.attrib["lemma"] = lem_rest
        ann.attrib["anchor"] = ann.attrib["anchor"].split(" ", 1)[1]

    transform_blocks(eq_matcher("annotation"), inf, ann_reanchor, outf)


@munge.command("babelnet-lookup")
@click.argument("inf", type=click.File("rb"))
@click.argument("map_bn2wn", type=click.File("r"))
@click.argument("outf", type=click.File("wb"))
def babelnet_lookup(inf: IO, map_bn2wn: IO, outf: IO):
    """
    This stage converts BabelNet ids to WordNet ids.
    """
    bn2wn_map: Dict[str, Set[str]] = {}
    for line in map_bn2wn:
        bn, wn_full = line[:-1].split("\t")
        wn_off = wn_full.split(":", 1)[1]
        bn2wn_map.setdefault(bn, set()).add(wn_off)

    def ann_bn2wn(ann):
        if ann.text not in bn2wn_map:
            return BYPASS
        wn_ids = bn2wn_map[ann.text]
        bits = []
        for wn_id in wn_ids:
            off, pos = wn_id[:-1], wn_id[-1]
            bits.append("{}-{}".format(off, pos))
        ann.text = " ".join(bits)

    transform_blocks(eq_matcher("annotation"), inf, ann_bn2wn, outf)


def lexical_sample_head(outf):
    outf.write(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE corpus SYSTEM "lexical-sample.dtd">
<corpus lang="finnish">
"""
    )


def lexical_sample_foot(outf):
    outf.write("</corpus>\n")


@contextmanager
def lexical_sample(outf):
    lexical_sample_head(outf)
    yield
    lexical_sample_foot(outf)


def lexelt_head(lemma_str, pos_chr, outf):
    outf.write("""<lexelt item="{}" pos="{}">\n""".format(lemma_str, pos_chr))


def lexelt_foot(outf):
    outf.write("</lexelt>\n")


@contextmanager
def lexelt(lemma_str, pos_chr, outf):
    lexelt_head(lemma_str, pos_chr, outf)
    yield
    lexelt_foot(outf)


@contextmanager
def instance(inst, out_f):
    out_f.write("""<instance id="{}">\n""".format(inst.attrib["id"]))
    yield
    out_f.write("</instance>\n")


def write_context(sent_elem, inst, out_f):
    out_f.write("<context>\n")
    for idx, elem in enumerate(sent_elem.xpath("instance|wf")):
        if idx > 0:
            out_f.write(" ")
        if elem == inst:
            out_f.write("<head>")
        out_f.write(escape(elem.text))
        if elem == inst:
            out_f.write("</head>")
    out_f.write("\n</context>\n")


@munge.command("unified-to-senseval")
@click.argument("inf", type=click.File("rb"))
@click.argument("keyin", type=click.File("r"))
@click.argument("outdir", type=click.Path())
def unified_to_senseval(inf: IO, keyin: IO, outdir: str):
    """

    Converts from the unified format to a Senseval-3 -style format in
    individual files. The resulting files should be directly usable to train a
    single word model with ItMakesSense or can be gathered using.

    This is a scatter type operation.
    """
    out_files: Dict[str, str] = {}
    for sent_elem in iter_sentences(inf):
        for inst in sent_elem.xpath("instance"):
            lemma_str = inst.attrib["lemma"].lower()
            pos_str = inst.attrib["pos"]
            pos_chr = UNI_POS_WN_MAP[pos_str]
            lemma_pos = "{}.{}".format(lemma_str, pos_chr)

            # Write XML
            out_dir = pjoin(outdir, lemma_pos)
            if lemma_pos not in out_files:
                makedirs(out_dir, exist_ok=True)
                out_fn = pjoin(out_dir, "train.xml")
                out_f = open(out_fn, "w")
                lexical_sample_head(out_f)
                lexelt_head(lemma_str, pos_chr, out_f)
            else:
                out_fn = out_files[lemma_pos]
                out_f = open(out_fn, "a")
            with instance(inst, out_f):
                write_context(sent_elem, inst, out_f)
            out_f.close()

            # Write key file
            key_fn = pjoin(out_dir, "train.key")
            key_line = keyin.readline()
            key_id, key_synset = key_line.rstrip().split(" ", 1)
            assert key_id == inst.attrib["id"]
            if lemma_pos not in out_files:
                key_f = open(key_fn, "w")
            else:
                key_f = open(key_fn, "a")
            out_line = "{} {} {}\n".format(lemma_pos, key_id, key_synset)
            key_f.write(out_line)
            key_f.close()

            # Add to out_files
            if lemma_pos not in out_files:
                out_files[lemma_pos] = out_fn

    for out_fn in out_files.values():
        with open(out_fn, "a") as out_f:
            lexelt_foot(out_f)
            lexical_sample_foot(out_f)


@munge.command("senseval-gather")
@click.argument("indir", type=click.Path())
@click.argument("outf", type=click.File("w"))
@click.argument("keyout", type=click.File("w"))
def senseval_gather(indir: str, outf: IO, keyout: IO):
    """
    Gather individual per-word SenseEval files into one big file, usable by
    ItMakesSense and Context2Vec.
    """
    with lexical_sample(outf):
        for word_dir in listdir(indir):
            train_fn = pjoin(indir, word_dir, "train.xml")
            key_fn = pjoin(indir, word_dir, "train.key")
            with open(train_fn, "rb") as train_f:
                stream = etree.iterparse(train_f, events=("start", "end"))

                def cb(lexelt):
                    if not len(lexelt):
                        return
                    outf.write(etree.tostring(lexelt, encoding="unicode"))

                chunk_cb(stream, eq_matcher("lexelt"), cb)

            with open(key_fn) as key_f:
                keyout.write(key_f.read())


@munge.command("unified-key-to-ims-test")
@click.argument("keyin", type=click.File("r"))
@click.argument("keyout", type=click.File("w"))
def unified_key_to_ims_test(keyin: IO, keyout: IO):
    for line in keyin:
        bits = line.split(" ")
        iden = bits[1]
        guesses = bits[2:]
        keyout.write("{} {}".format(iden, " ".join(guesses)))


HEAD_REGEX = re.compile("(.*)<head>(.*)</head>(.*)")


@munge.command("finnpos-senseval")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def finnpos_senseval(inf: IO, outf: IO):
    from stiff.munge.pos import finnpos_senseval as finnpos_senseval_impl

    return finnpos_senseval_impl(inf, outf)


@munge.command("omorfi-segment-senseval")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def omorfi_segment_senseval(inf: IO, outf: IO):
    from stiff.munge.seg import omorfi_segment_senseval as omorfi_segment_senseval_impl

    return omorfi_segment_senseval_impl(inf, outf)


@munge.command("man-ann-select")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--source", default=None)
@click.option("--end", default=None)
def man_ann_select(inf: IO, outf: IO, source, end):
    stream = etree.iterparse(inf, events=("start", "end"))
    inside = False
    matches = False
    missing_text = False
    stopped = False
    for event, elem in stream:
        if event == "start" and elem.tag == "corpus":
            inside = True
            matches = source is None or elem.attrib["source"] == source

        if (
            (not inside)
            or (inside and matches and not stopped)
            or (stopped and elem.tag == "corpus")
        ):
            if missing_text and elem.getparent() is not None:
                fixup_missing_text(event, elem, outf)
            missing_text = write_event(event, elem, outf)

        if event == "end" and elem.tag == "corpus":
            inside = False
            stopped = False
        if (
            event == "end"
            and elem.tag == "sentence"
            and end is not None
            and elem.attrib["id"] == end
        ):
            stopped = True


@munge.command("stiff-select-wn")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option(
    "--wn",
    type=click.Choice(["fin", "qf2", "qwf"]),
    default=["qf2"],
    multiple=True,
    help="Which WordNet (multiple allowed) to use: OMW FiWN, "
    "FiWN2 or OMW FiWN wikitionary based extensions",
)
def stiff_select_wn(inf: IO, outf: IO, wn):
    from stiff.munge.utils import langs_of_wns

    selected_wns = set(wn)
    selected_langs = langs_of_wns(selected_wns)

    def filter_wns(wns):
        return [wn for wn in wns if wn in selected_wns]

    def select_wn(ann):
        # annotation[wordnets]
        ann_wns = ann.attrib["wordnets"].split()
        common_wns = filter_wns(ann_wns)
        if not len(common_wns):
            return BYPASS
        ann.attrib["wordnets"] = " ".join(common_wns)

        # annotation[wnlemma]
        wnlemma_bits = ann.attrib["wnlemma"].split(" ")
        new_wmlemmas_bits = []
        for wnlemma in wnlemma_bits:
            wnlemma_dict = parse_qs_single(wnlemma)
            wnlemma_wns = wnlemma_dict["wn"].split(",")
            common_wns = filter_wns(wnlemma_wns)
            if not common_wns:
                continue
            wnlemma_dict["wn"] = ",".join(common_wns)
            new_wmlemmas_bits.append(urlencode(wnlemma_dict))
        ann.attrib["wnlemma"] = " ".join(new_wmlemmas_bits)

        # annotation > #text
        ann_langs = langs_of_wns(ann_wns)
        if len(ann_langs) <= len(selected_langs):
            return
        lemmas_str = ann.text
        bits = lemmas_str.split(" ")
        assert len(bits) <= 2
        if len(bits) <= 1:
            return
        if "eng" in selected_langs:
            ann.text = bits[0]
        else:
            ann.text = bits[1]

    transform_blocks(eq_matcher("annotation"), inf, select_wn, outf)


@munge.command("senseval-select-lemma")
@click.argument("inf", type=click.File("rb"))
@click.argument("keyin", type=click.File("r"))
@click.argument("outf", type=click.File("wb"))
@click.argument("keyout", type=click.File("w"))
@click.argument("lemma_pos")
def senseval_select_lemma(inf, keyin, outf, keyout, lemma_pos):
    if "." in lemma_pos:
        lemma, pos = lemma_pos.rsplit(".", 1)
    else:
        lemma = lemma_pos
        pos = None

    keys = set()

    def filter_lexelt(lexelt):
        if lexelt.attrib["item"] != lemma:
            return BYPASS
        if pos and lexelt.attrib["pos"] != pos:
            return BYPASS
        for instance in lexelt:
            keys.add(instance.attrib["id"])

    transform_blocks(eq_matcher("lexelt"), inf, filter_lexelt, outf)

    for line in keyin:
        if line.split(" ", 1)[0] not in keys:
            continue
        keyout.write(line)


@munge.command("senseval-rm-lemma")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.argument("rm_key_out", type=click.File("wb"), required=False)
@click.option("--lemmas")
def senseval_rm_lemma(inf, outf, rm_key_out=None, lemmas=None):
    lemmas = lemmas.split(",") if lemmas else []

    rm_keys = set()

    def filter_lexelt(lexelt):
        if str(lexelt.attrib["item"]) in lemmas:
            if rm_key_out:
                for instance in lexelt:
                    rm_keys.add(instance.attrib["id"])
            return BYPASS

    transform_blocks(eq_matcher("lexelt"), inf, filter_lexelt, outf)

    if rm_key_out:
        pickle.dump(rm_keys, rm_key_out)


@munge.command("key-rm-lemma")
@click.argument("inf", type=click.File("r"))
@click.argument("outf", type=click.File("w"))
@click.argument("rm_key_in", type=click.File("r"))
@click.option("--three/--two")
def key_rm_lemma(inf, outf, rm_key_in, three):
    rm_keys = pickle.load(rm_key_in)
    for line in inf:
        if (three and line.split(" ", 2)[1] in rm_keys) or (
            not three and line.split(" ", 1)[0] in rm_keys
        ):
            continue
        outf.write(line)


if __name__ == "__main__":
    munge()
