import click
from filter_utils import iter_sentences, transform_sentences, transform_blocks
from xml.sax.saxutils import escape
from urllib.parse import parse_qsl
import pygtrie


WN_UNI_POS_MAP = {"n": "NOUN", "v": "VERB", "a": "ADJ", "r": "ADV"}


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
                        lemma.replace("#", "|").replace(" ", "_"),
                        pos,
                        sense_key,
                        match_anchor,
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


@munge.command("babelnet-lookup")
@click.argument("inf", type=click.File("rb"))
@click.argument("map_bn2wn", type=click.File("r"))
@click.argument("outf", type=click.File("wb"))
def babelnet_lookup(inf, map_bn2wn, outf):
    bn2wn_map = {}
    for line in map_bn2wn:
        bn, wn_full = line[:-1].split("\t")
        wn_off = wn_full.split(":", 1)[1]
        bn2wn_map[bn] = wn_off

    def ann_bn2wn(ann):
        if ann.text not in bn2wn_map:
            return True
        wn_id = bn2wn_map[ann.text]
        off, pos = wn_id[:-1], wn_id[-1]
        ann.text = "{}-{}".format(off, pos)

    transform_blocks("annotation", inf, ann_bn2wn, outf)


if __name__ == "__main__":
    munge()
