import click
from typing import IO

from stiff.data.fixes import fix_all

from stiff.data.constants import DEFAULT_SAMPLE_LINES, DEFAULT_SAMPLE_MAX
from stiff.writers import AnnWriter, man_ann_ann
from stiff.extract import FinExtractor
from stiff.corpus_read import read_opensubtitles2018
from stiff.utils import parse_qs_single, wnlemma_to_analy_lemma
from stiff.utils.xml import transform_blocks, in_matcher

from lxml import etree
from conllu import parse_incr


fix_all()


def man_ann_line(extractor: FinExtractor, writer: AnnWriter, fi_tok: str):
    tagging = extractor.extract(fi_tok)
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
    extractor = FinExtractor()
    with AnnWriter(output) as writer:
        for (
            idx,
            _zh_untok,
            _zh_tok,
            fi_tok,
            srcs,
            imdb_id,
            new_imdb_id,
            align,
        ) in read_opensubtitles2018(corpus):
            if idx >= DEFAULT_SAMPLE_MAX:
                break
            if new_imdb_id:
                if idx > 0:
                    writer.end_subtitle()
                writer.begin_subtitle(srcs, imdb_id)
            if idx in DEFAULT_SAMPLE_LINES:
                man_ann_line(extractor, writer, fi_tok)
            writer.inc_sent()
        writer.end_subtitle()


@man_ann.command("filter")
@click.argument("input", type=click.File("rb"))
@click.argument("output", type=click.File("wb"))
def filter(input: IO, output: IO):
    extractor = FinExtractor()
    text = None

    def proc(elem):
        nonlocal text
        if elem.tag == "text":
            text = elem.text
        else:
            tagging = extractor.extract(text)
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

    output.write(
        """<?xml version="1.0" encoding="UTF-8"?>
<corpus source="{}">
""".format(
            source
        )
    )
    for sent in parse_incr(input):
        output.write('<sentence id="{}">\n'.format(sent.metadata["sent_id"]))
        output.write(
            '<text lang="fi">{}</text>\n'.format(
                " ".join(token["form"] for token in sent)
            )
        )
        output.write("<annotations></annotations>\n")
        output.write("</sentence>\n")
    output.write("</corpus>\n")


def key_ann(ann):
    from stiff.munge.utils import synset_id_of_ann

    token_idx = int(parse_qs_single(ann.attrib["anchor-positions"])["token"])
    return (token_idx, ann.attrib["anchor"], synset_id_of_ann(ann))


def key_tok_tag(tok, tag):
    from stiff.wordnet.fin import Wordnet as WordnetFin

    return (tok.anchors[0].token, tok.token, tag.canonical_synset_id(WordnetFin))


@man_ann.command("reann")
@click.argument("input", type=click.File("rb"))
@click.argument("output", type=click.File("wb"))
def reann(input: IO, output: IO):
    extractor = FinExtractor()
    text = None

    def proc(elem):
        nonlocal text
        if elem.tag == "text":
            text = elem.text
        else:
            valid = {}
            for ann in elem.xpath("annotation"):
                lemmas = []
                if "&" not in ann.attrib["wnlemma"]:
                    lemmas.append(wnlemma_to_analy_lemma(ann.attrib["wnlemma"]))
                lemmas.append(ann.attrib["lemma"])
                valid[key_ann(ann)] = lemmas
            comments = {}
            for comment in elem.xpath("comment()"):
                if "XXX:" not in comment.text:
                    continue
                prev_annotation = comment.xpath("preceding-sibling::annotation")
                if prev_annotation:
                    key = key_ann(prev_annotation[-1])
                else:
                    key = None
                comments[key] = etree.tostring(comment, encoding="unicode")
            processed = set()

            tagging = extractor.extract(text)
            anns = []
            if None in comments:
                anns.append(comments[None])
            bests = {}
            for tok in tagging.tokens:
                for tag in tok.tags:
                    match = key_tok_tag(tok, tag)
                    if match not in valid or tag.lemma not in valid[match]:
                        continue
                    cur_priority = valid[match].index(tag.lemma)
                    if match in bests:
                        if bests[match][0] < cur_priority:
                            continue
                        assert bests[match][0] != cur_priority
                    bests[match] = (cur_priority, tok, tag)

            for _idx, tok, tag in bests.values():
                match = key_tok_tag(tok, tag)
                assert match not in processed
                anns.append(man_ann_ann("fi", tok, tag))
                if match in comments:
                    anns.append(comments[match])
                processed.add(match)
            new_elem = etree.fromstring("<div>{}</div>".format("".join(anns)))
            elem[:] = new_elem[:]
            assert len(valid) == len(processed)

    transform_blocks(in_matcher("text", "annotations"), input, proc, output)


if __name__ == "__main__":
    man_ann()
