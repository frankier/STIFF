import re
from lxml import etree
import sys
import click
from stiff.filter_utils import (
    iter_sentences,
    transform_sentences,
    transform_blocks,
    BYPASS,
    chunk_cb,
)
from xml.sax.saxutils import escape
from urllib.parse import parse_qsl
import pygtrie
from stiff.data import WN_UNI_POS_MAP, UNI_POS_WN_MAP
from finntk.wordnet.reader import fiwn, get_en_fi_maps
from finntk.wordnet.utils import post_id_to_pre, pre2ss
from finntk.omor.extract import lemma_intersect
from finntk.finnpos import sent_finnpos
from os.path import join as pjoin
from os import makedirs, listdir
from contextlib import contextmanager


@click.group("munge")
def munge():
    """
    Munge between different stream/corpus formats.
    """
    pass


@munge.command("stiff-to-unified")
@click.argument("stiff", type=click.File("rb"))
@click.argument("unified", type=click.File("w"))
def stiff_to_unified(stiff, unified):
    """
    Do the XML conversion from the STIFF format (similar to the Eurosense
    format) to the Unified format. Note that this assumes is that previous
    filtering has produced an unambiguous tagging.
    """
    unified.write('<?xml version="1.0" encoding="UTF-8" ?>\n')
    unified.write('<corpus lang="fi" source="stiff">\n')
    unified.write('<text id="stiff">\n')

    for sent_elem in iter_sentences(stiff):
        unified.write(
            '<sentence id="stiff.{:08d}">\n'.format(int(sent_elem.attrib["id"]))
        )
        text_elem = sent_elem.xpath("text")[0]
        text_id = text_elem.attrib["id"]
        anns = []
        for ann in sent_elem.xpath(".//annotation"):
            our_pos = None
            for pos_enc in ann.attrib["anchor-positions"].split(" "):
                pos = dict(parse_qsl(pos_enc))
                if pos["from"] == text_id:
                    our_pos = pos
            assert our_pos is not None, "Didn't find a usable anchor position"
            char_id = int(our_pos["char"])
            anns.append((char_id, ann.attrib["anchor"], ann.attrib["lemma"], ann.text))
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
                unified.write(
                    '<instance lemma="{}" key="{}">{}</instance>\n'.format(
                        instance["lemma"], " ".join(instance["key"]), instance["anchor"]
                    )
                )
                cursor += len(instance["anchor"]) + 1
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
def unified_split(inf, outf, keyout):
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


@munge.command("eurosense-to-unified")
@click.argument("eurosense", type=click.File("rb", lazy=True))
@click.argument("unified", type=click.File("w"))
def eurosense_to_unified(eurosense, unified):
    """
    Do the XML conversion from the Eurosense format to the Unified format. Note
    that this only deals with XML and doesn't convert other things like synset
    ids. For the full conversion pipeline see eurosense2unified in
    `pipeline.py`.
    """
    unified.write('<?xml version="1.0" encoding="UTF-8" ?>\n')
    unified.write('<corpus lang="fi" source="eurosense">\n')
    unified.write('<text id="eurosense">\n')
    for sent_elem in iter_sentences(eurosense):
        unified.write(
            '<sentence id="eurosense.{:08d}">\n'.format(int(sent_elem.attrib["id"]))
        )
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
def eurosense_fix_lemmas(inf, outf, keep_unknown, quiet):
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

    transform_blocks("annotation", inf, ann_fix_lemmas, outf)


@munge.command("eurosense-reanchor")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def eurosense_reanchor(inf, outf):
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
        for lemma_name in all_lemma_names:
            if lemma_name.split("_", 1)[0] == lem_begin:
                return
        ann.attrib["lemma"] = lem_rest
        ann.attrib["anchor"] = ann.attrib["anchor"].split(" ", 1)[1]

    transform_blocks("annotation", inf, ann_reanchor, outf)


@munge.command("babelnet-lookup")
@click.argument("inf", type=click.File("rb"))
@click.argument("map_bn2wn", type=click.File("r"))
@click.argument("outf", type=click.File("wb"))
def babelnet_lookup(inf, map_bn2wn, outf):
    """
    This stage converts BabelNet ids to WordNet ids.
    """
    bn2wn_map = {}
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

    transform_blocks("annotation", inf, ann_bn2wn, outf)


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


def lexelt_head(lemma_str, outf):
    outf.write("""<lexelt item="{}">\n""".format(lemma_str))


def lexelt_foot(outf):
    outf.write("</lexelt>\n")


@contextmanager
def lexelt(lemma_str, outf):
    lexelt_head(lemma_str, outf)
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
def unified_to_senseval(inf, keyin, outdir):
    """

    Converts from the unified format to a Senseval-3 -style format in
    individual files. The resulting files should be directly usable to train a
    single word model with ItMakesSense or can be gathered using.

    This is a scatter type operation.
    """
    out_files = {}
    for sent_elem in iter_sentences(inf):
        for inst in sent_elem.xpath("instance"):
            lemma_str = inst.attrib["lemma"].lower()
            pos_str = inst.attrib["pos"]
            lemma_pos = "{}.{}".format(lemma_str, UNI_POS_WN_MAP[pos_str])

            # Write XML
            out_dir = pjoin(outdir, lemma_pos)
            if lemma_pos not in out_files:
                makedirs(out_dir, exist_ok=True)
                out_fn = pjoin(out_dir, "train.xml")
                out_f = open(out_fn, "w")
                lexical_sample_head(out_f)
                lexelt_head(lemma_pos, out_f)
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
def senseval_gather(indir, outf, keyout):
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
                    outf.write(etree.tostring(lexelt, encoding="unicode"))

                chunk_cb(stream, "lexelt", cb)

            with open(key_fn) as key_f:
                keyout.write(key_f.read())


@munge.command("unified-key-to-ims-test")
@click.argument("keyin", type=click.File("r"))
@click.argument("keyout", type=click.File("w"))
def unified_key_to_ims_test(keyin, keyout):
    for line in keyin:
        bits = line.split(" ")
        iden = bits[1]
        guesses = bits[2:]
        keyout.write("{} {}".format(iden, " ".join(guesses)))


HEAD_REGEX = re.compile("(.*)<head>(.*)</head>(.*)")


@munge.command("finnpos-senseval")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def finnpos_senseval(inf, outf):
    def fmt_analy(analy):
        surf, lemma, tags = analy
        return "{}/{}/{}".format(surf, lemma, tags["pos"])

    def transform_context(context):
        sent = []
        before = context.text
        head_tag = context[0]
        head = head_tag.text
        after = head_tag.tail

        before_tok = before.strip().split(" ")
        head_tok = head.split(" ")
        after_tok = after.strip().split(" ")

        sent = before_tok + head_tok + after_tok
        analysed = sent_finnpos(sent)

        ana_before = analysed[: len(before_tok)]
        ana_head = analysed[len(before_tok) : len(before_tok) + len(head_tok)]
        ana_after = analysed[len(before_tok) + len(head_tok) :]

        context.text = "".join(fmt_analy(ana) + " " for ana in ana_before)
        head_tag.text = " ".join(fmt_analy(ana) for ana in ana_head)
        head_tag.tail = "".join(" " + fmt_analy(ana) for ana in ana_after)
        return context

    transform_blocks("context", inf, transform_context, outf)


if __name__ == "__main__":
    munge()
