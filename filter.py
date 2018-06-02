import click
from filter_utils import transform_sentences


@click.group()
def filter():
    pass


@filter.command("no-support")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def filter_support(inf, outf):
    def remove_no_support(elem):
        for ann in elem.iter("annotation"):
            if ann.attrib["support"]:
                continue
            ann.getparent().remove(ann)

    transform_sentences(inf, remove_no_support, outf)


@filter.command("lang")
@click.argument("lang")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def filter_lang(lang, inf, outf):
    def remove_other_langs(elem):
        for ann in elem.iter("text", "annotation"):
            if ann.attrib["lang"] == lang:
                continue
            ann.getparent().remove(ann)

    transform_sentences(inf, remove_other_langs, outf)


@filter.command("align-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def filter_align_dom(inf, outf):
    def remove_dom_transfer(sent):
        anns = sent.xpath('/annotation[starts-with(@support, "aligned-transfer:")]]')
        for ann in anns:
            dominated = sent.xpath(
                (
                    '/annotation[starts-with(@support, "transfer:")]'
                    '[@anchor-positions="{}"]'
                ).format(ann["anchor-positions"])
            )
            for dom in dominated:
                dom.getparent().remove(dom)

    transform_sentences(inf, remove_dom_transfer, outf)


if __name__ == "__main__":
    filter()
