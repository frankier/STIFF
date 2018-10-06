import click

from stiff.extract import CmnExtractor, FinExtractor
from stiff.writers import Writer
from stiff.corpus_read import read_opensubtitles2018
from stiff.tag import proc_line


@click.command("tag")
@click.argument("corpus")
@click.argument("output", type=click.File("w"))
@click.option("--cutoff", default=None, type=int)
@click.option("--skip-until")
def tag(corpus, output, cutoff, skip_until):
    """
    Tag Finnish and Chinese parts of OpenSubtitles2018 by writing all possible
    taggings for each token, and adding ways in which tagging from the two
    languages support each other. This can be made into an unambiguously tagged
    corpus filtering with the other scripts in this repository.
    """
    cmn_extractor = CmnExtractor()
    fin_extractor = FinExtractor()
    skipping = True
    with Writer(output) as writer:
        for (
            idx,
            zh_untok,
            zh_tok,
            fi_tok,
            srcs,
            imdb_id,
            new_imdb_id,
            align,
        ) in read_opensubtitles2018(corpus):
            if skip_until and skipping:
                if skip_until == imdb_id:
                    skipping = False
                else:
                    continue
            if new_imdb_id:
                if idx > 0:
                    writer.end_subtitle()
                writer.begin_subtitle(srcs, imdb_id)
            proc_line(
                cmn_extractor, fin_extractor, writer, zh_untok, zh_tok, fi_tok, align
            )
            if cutoff is not None and idx > cutoff:
                break
        writer.end_subtitle()


if __name__ == "__main__":
    tag()
