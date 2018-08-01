import os
import sys
import click
from plumbum.cmd import python, cat


dir = os.path.dirname(os.path.realpath(__file__))
filter_py = os.path.join(dir, "filter.py")
munge_py = os.path.join(dir, "munge.py")


@click.group()
def pipeline():
    pass


def add_head(pipeline, head):
    if head is not None:
        pipeline = pipeline | python[filter_py, "head", "--sentences", head, "-", "-"]
    return pipeline


@pipeline.command("eurosense2unified")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("outf", type=click.Path())
@click.argument("keyout", type=click.Path())
@click.option("--head", default=None)
@click.option("--babel2wn-map", envvar="BABEL2WN_MAP", required=True)
def eurosense2unified(inf, outf, keyout, head, babel2wn_map):
    pipeline = add_head(cat[inf], head)
    pipeline = (
        pipeline
        | python[filter_py, "lang", "fi", "-", "-"]
        | python[munge_py, "babelnet-lookup", "-", babel2wn_map, "-"]
        | python[munge_py, "eurosense-reanchor", "-", "-"]
        | python[munge_py, "eurosense-lemma-fix", "--drop-unknown", "-", "-"]
        | python[filter_py, "rm-empty", "-", "-"]
        | python[munge_py, "eurosense-to-unified", "-", "-"]
        | python[munge_py, "unified-split", "-", outf, keyout]
    )
    pipeline(retcode=[-13, 0], stderr=sys.stderr)


@pipeline.command("proc-stiff")
@click.argument("method")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("outf", type=click.Path())
@click.option("--head", default=None)
def proc_stiff(method, inf, outf, head):
    from plumbum.cmd import zstdcat, zstdmt

    pipeline = add_head(zstdcat["-D", "zstd-compression-dictionary", inf], head)
    if method == "simple":
        pipeline = (
            pipeline
            | python[filter_py, "no-support", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "rm-empty", "-", "-"]
        )
    elif method == "complex":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
        )
    else:
        assert False, "Unknown method"
    pipeline = pipeline | zstdmt["-D", "zstd-compression-dictionary", "-", "-o", outf]
    pipeline(retcode=[-13, 0])


if __name__ == "__main__":
    pipeline()
