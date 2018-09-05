import click
from typing import IO

import stiff.fixes  # noqa

from stiff.data import DEFAULT_SAMPLE_LINES, DEFAULT_SAMPLE_MAX
from stiff.writers import AnnWriter, man_ann_ann
from stiff.extract import extract_full_fin
from stiff.corpus_read import read_opensubtitles2018
from stiff.filter_utils import transform_blocks, in_matcher

from lxml import etree
from conllu import parse_incr


def man_ann_line(writer: AnnWriter, fi_tok: str):
    tagging = extract_full_fin(fi_tok)
    writer.begin_sent()
    writer.write_text("fi", fi_tok)
    writer.start_anns()
    for tok in tagging.tokens:
        for tag in tok.tags:
            writer.write_ann("fi", tok, tag)
    writer.end_anns()
    writer.end_sent()


@click.group("man-ann")
def man_ann():
    """
    Create a file containing all possible annotations, so incorrect ones can be deleted so as to create a manual annotation.
    """
    pass


@man_ann.command("opensubs18")
@click.argument("corpus")
@click.argument("output", type=click.File("w"))
def opensubs18(corpus: str, output: IO):
    with AnnWriter(output) as writer:
        for idx, _zh_untok, _zh_tok, fi_tok, srcs, imdb_id, new_imdb_id, align in read_opensubtitles2018(corpus):
            if idx >= DEFAULT_SAMPLE_MAX:
                break
            if new_imdb_id:
                if idx > 0:
                    writer.end_subtitle()
                writer.begin_subtitle(srcs, imdb_id)
            if idx in DEFAULT_SAMPLE_LINES:
                man_ann_line(writer, fi_tok)
            writer.inc_sent()
        writer.end_subtitle()


@man_ann.command("filter")
@click.argument("input", type=click.File("rb"))
@click.argument("output", type=click.File("wb"))
def filter(input: IO, output: IO):
    text = None

    def proc(elem):
        nonlocal text
        if elem.tag == "text":
            text = elem.text
        else:
            tagging = extract_full_fin(text)
            anns = []
            for tok in tagging.tokens:
                for tag in tok.tags:
                    anns.append(man_ann_ann("fi", tok, tag))
            new_elem = etree.fromstring("<div>{}</div>".format("".join(anns)))
            elem[:] = new_elem[:]

    transform_blocks(in_matcher("text", "annotations"), input, proc, output)


@man_ann.command("conllu-gen")
@click.argument("input", type=click.File("r"))
@click.argument("output", type=click.File("w"))
@click.option("--source", nargs=1, default="tdt")
def conllu_gen(input: IO, output: IO, source: str):

    output.write("""<?xml version="1.0" encoding="UTF-8"?>
<corpus source="{}">
""".format(source))
    for sent in parse_incr(input):
        output.write('<sentence id="{}">\n'.format(sent.metadata['sent_id']))
        output.write('<text lang="fi">{}</text>\n'.format(" ".join(token['form'] for token in sent)))
        output.write("<annotations></annotations>\n")
        output.write("</sentence>\n")
    output.write("</corpus>\n")


if __name__ == "__main__":
    man_ann()
