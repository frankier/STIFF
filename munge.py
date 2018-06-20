import sys
import click
from filter_utils import iter_sentences, transform_sentences, transform_blocks, BYPASS
from xml.sax.saxutils import escape
from urllib.parse import parse_qsl
import pygtrie
from data import WN_UNI_POS_MAP
from finntk.wordnet.reader import fiwn, get_en_fi_maps
from finntk.wordnet.utils import post_id_to_pre, pre2ss
from finntk.omor.extract import lemma_intersect


@click.group("munge")
def munge():
    pass


@munge.command("stiff-to-unified")
@click.argument("stiff", type=click.File("rb"))
@click.argument("unified", type=click.File("w"))
def stiff_to_unified(stiff, unified):
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


if __name__ == "__main__":
    munge()
