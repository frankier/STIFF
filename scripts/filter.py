import click
from stiff.filter_utils import transform_sentences, BYPASS, BREAK
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
def rm_empty(inf, outf):
    """
    Remove sentences with no annotations.
    """

    def remove_empty(elem):
        if len(elem.xpath("./annotations/annotation")) == 0:
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


if __name__ == "__main__":
    filter()
