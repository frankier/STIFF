from lxml import etree
import click
from stiff.utils.xml import (
    fixup_missing_text,
    transform_sentences,
    write_event,
    BYPASS,
    BREAK,
    free_elem,
    close_all,
)
from stiff.data import DEFAULT_SAMPLE_LINES, DEFAULT_SAMPLE_MAX
from urllib.parse import parse_qs, urlencode


@click.group()
def filter():
    """
    Filter the master STIFF corpus to produce less ambiguous or unambiguous
    versions.
    """
    pass


@filter.command("no-support")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def filter_support(inf, outf):
    """
    Remove annotations without any support at all.
    """

    def remove_no_support(elem):
        for ann in elem.xpath("./annotations/annotation"):
            if ann.attrib["support"]:
                continue
            ann.getparent().remove(ann)

    transform_sentences(inf, remove_no_support, outf)


@filter.command("lang")
@click.argument("lang")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def filter_lang(lang, inf, outf):
    """
    Change a multilingual corpus to a monolingual one by selecting a single
    language.
    """

    def remove_other_langs(elem):
        for ann in elem.xpath("./annotations/annotation | ./text"):
            if ann.attrib["lang"] == lang:
                continue
            ann.getparent().remove(ann)

    transform_sentences(inf, remove_other_langs, outf)


@filter.command("fold-support")
@click.argument("lang")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def fold_support(lang, inf, outf):
    """
    Move information about how an annotation is connected to a wordnet how it
    is anchored into annotations which it supports in LANG.
    """

    def tran(elem):
        xpath = "./annotations/annotation[@lang='{}']".format(lang)
        for ann in elem.xpath(xpath):
            support = ann.attrib.get("support")
            if not support:
                continue
            new_support = []
            for supp in support.split(" "):
                supp = parse_qs(supp)
                trans_from = supp["transfer-from"][0]
                from_elem = elem.xpath(
                    "./annotations/annotation[@id='{}']".format(trans_from)
                )[0]
                from_wordnets = from_elem.attrib["wordnets"]
                for position in from_elem.attrib["anchor-positions"].split(" "):
                    from_anchor = parse_qs(position)
                    from_source = from_anchor["from"]
                from_lemma_path = from_elem.attrib["lemma-path"]
                del supp["transfer-from"]
                supp.update(
                    {
                        "transfer-from-wordnets": from_wordnets,
                        "transfer-from-source": from_source,
                        "transfer-from-lemma-path": from_lemma_path,
                    }
                )
                new_support.append(urlencode(supp))
            ann.attrib["support"] = " ".join(new_support)

    transform_sentences(inf, tran, outf)


@filter.command("rm-empty")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--text/--annotations")
def rm_empty(inf, outf, text):
    """
    Remove sentences with no annotations, or optionally with no text instead.
    """

    def remove_empty(elem):
        if (
            len(elem.xpath("./text")) == 0
            if text
            else len(elem.xpath("./annotations/annotation")) == 0
        ):
            return BYPASS

    transform_sentences(inf, remove_empty, outf)


@filter.command("align-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def filter_align_dom(inf, outf):
    """
    Dominance filter:

    Remove annotations which are based on unaligned transfers when there is an
    annotation based on aligned transfers of the same token.
    """

    def remove_dom_transfer(sent):
        anns = sent.xpath(
            './annotations/annotation[starts-with(@support, "aligned-transfer:")]]'
        )
        for ann in anns:
            dominated = sent.xpath(
                (
                    './annotations/annotation[starts-with(@support, "transfer:")]'
                    '[@anchor-positions="{}"]'
                ).format(ann["anchor-positions"])
            )
            for dom in dominated:
                dom.getparent().remove(dom)

    transform_sentences(inf, remove_dom_transfer, outf)


@filter.command("head")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--sentences", default=100)
def head(inf, outf, sentences):
    """
    Take the first SENTENCES sentences from INF.
    """
    seen_sents = 0

    def count_break_sent(sent):
        nonlocal seen_sents
        if seen_sents >= sentences:
            return BREAK
        seen_sents += 1

    transform_sentences(inf, count_break_sent, outf)
    inf.close()
    outf.close()


@filter.command("sample")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def sample(inf, outf):
    """
    Sample the sentences in DEFAULT_SAMPLE_LINES (fixed) from inf
    """
    seen_sents = 0

    def count_break_sent(sent):
        nonlocal seen_sents
        if seen_sents >= DEFAULT_SAMPLE_MAX:
            return BREAK
        if seen_sents not in DEFAULT_SAMPLE_LINES:
            seen_sents += 1
            return BYPASS
        seen_sents += 1

    transform_sentences(inf, count_break_sent, outf)

    if seen_sents <= max(DEFAULT_SAMPLE_LINES):
        print("Not enough sentences in input to sample.")


class MultiFile:
    def __init__(self, *fps):
        self.fps = fps

    def write(self, payload):
        for fp in self.fps:
            fp.write(payload)

    def close(self, payload):
        for fp in self.fps:
            fp.close(payload)


def split_xml(inf, testf, trainf, sentences):
    from io import BytesIO

    been_inside = False
    seen_sents = 0
    head_bio = BytesIO()
    outf = MultiFile(testf, head_bio)
    stream = etree.iterparse(inf, events=("start", "end"))
    started = False
    find_instance = False
    switch_instance = None
    for event, elem in stream:
        if started:
            fixup_missing_text(event, elem, outf)
        if event == "start" and elem.tag == "sentence":
            if not been_inside:
                outf = testf
            been_inside = True
            seen_sents += 1
        if find_instance and event == "start" and elem.tag == "instance":
            switch_instance = elem.attrib["id"]
            find_instance = False
        write_event(event, elem, outf)
        if event == "end" and elem.tag == "sentence":
            if seen_sents == sentences:
                close_all(elem, outf)
                outf = trainf
                outf.write(head_bio.getvalue())
                find_instance = True
            free_elem(elem)
        started = True
    return switch_instance


@filter.command("split")
@click.argument("inf", type=click.File("rb"))
@click.argument("testf", type=click.File("wb"))
@click.argument("trainf", type=click.File("wb"))
@click.argument("keyin", type=click.File("r"), required=False)
@click.argument("testkey", type=click.File("w"), required=False)
@click.argument("trainkey", type=click.File("w"), required=False)
@click.option("--sentences", default=100)
def split(inf, testf, trainf, keyin, testkey, trainkey, sentences):
    """
    Put the first SENTENCES sentences from INF into TESTF and the rest into
    TRAINF.
    """
    switch_instance = split_xml(inf, testf, trainf, sentences)

    if keyin:
        switched = False
        for line in keyin:
            if line.split()[0] == switch_instance:
                switched = True
            if switched:
                trainkey.write(line)
            else:
                testkey.write(line)


@filter.command("join")
@click.argument("infs", nargs=-1, type=click.File("r"))
@click.argument("outf", nargs=1, type=click.File("w"))
def join(infs, outf):
    outf.write("<?xml version='1.0' encoding='UTF-8'?>\n")
    outf.write("<corpora>\n")
    for inf in infs:
        for line in inf:
            if line.startswith("<?xml"):
                continue
            outf.write(line)
    outf.write("</corpora>\n")


if __name__ == "__main__":
    filter()
