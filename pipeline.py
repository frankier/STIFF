import click
from plumbum.cmd import zstdcat, python, zstdmt, cat


@click.group()
def pipeline():
    pass


def add_head(pipeline, head):
    if head is not None:
        pipeline = pipeline | python["filter.py", "head", "--sentences", head, "-", "-"]
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
        | python["filter.py", "lang", "fi", "-", "-"]
        | python["munge.py", "babelnet-lookup", "-", babel2wn_map, "-"]
        | python["filter.py", "rm-empty", "-", "-"]
        | python["munge.py", "eurosense-to-unified", "-", "-"]
        | python["munge.py", "unified-split", "-", outf, keyout]
    )
    (pipeline)(retcode=[-13, 0])


@pipeline.command("proc-stiff")
@click.argument("method")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("outf", type=click.Path())
@click.option("--head", default=None)
def proc_stiff(method, inf, outf, head):
    pipeline = add_head(zstdcat["-D", "zstd-compression-dictionary", inf], head)
    if method == "simple":
        pipeline = (
            pipeline
            | python["filter.py", "no-support", "-", "-"]
            | python["filter.py", "lang", "fi", "-", "-"]
            | python["filter.py", "rm-empty", "-", "-"]
        )
    else:
        assert False, "Unknown method"
    pipeline = pipeline | zstdmt["-D", "zstd-compression-dictionary", "-", "-o", outf]
    pipeline(retcode=[-13, 0])


if __name__ == "__main__":
    pipeline()
