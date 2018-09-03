import click

import stiff.fixes  # noqa

from stiff.writers import AnnWriter
from stiff.extract import get_anchor, get_synset_set_fin
from stiff.corpus_read import read_opensubtitles2018


def man_ann_line(writer, fi_tok):
    tagging = get_synset_set_fin(fi_tok)
    writer.begin_sent()
    writer.write_text("fi", fi_tok)
    writer.start_anns()
    for tok in tagging.tokens:
        anchor = get_anchor(tok)
        for tag in tok["tags"]:
            writer.write_ann("fi", anchor, tok, tag)
    writer.end_anns()
    writer.end_sent()


@click.command("man-ann")
@click.argument("corpus")
@click.argument("output", type=click.File("w"))
def man_ann(corpus, output):
    lines = list(range(17, 1000, 25))
    assert len(lines) == 40
    with AnnWriter(output) as writer:
        for idx, _zh_untok, _zh_tok, fi_tok, srcs, imdb_id, new_imdb_id, align in read_opensubtitles2018(corpus):
            if idx >= 1000:
                break
            if new_imdb_id:
                if idx > 0:
                    writer.end_subtitle()
                writer.begin_subtitle(srcs, imdb_id)
            if idx in lines:
                man_ann_line(writer, fi_tok)
            writer.inc_sent()
        writer.end_subtitle()


if __name__ == "__main__":
    man_ann()
