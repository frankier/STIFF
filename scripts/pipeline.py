import tempfile
import os
import sys
import click
from plumbum.cmd import cat, tee
from plumbum import local

python = local[sys.executable]

dir = os.path.dirname(os.path.realpath(__file__))
filter_py = os.path.join(dir, "filter.py")
munge_py = os.path.join(dir, "munge.py")
tag_py = os.path.join(dir, "tag.py")
man_ann_py = os.path.join(dir, "man_ann.py")


@click.group()
def pipeline():
    """
    These pipelines compose serveral filters and munges to convert between
    formats and filter STIFF.
    """
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
    """
    Convert from the Eurosense format to the Unified format so that Eurosense
    tagged data can be compared with STIFF.
    """
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
    """
    Do one of several standard STIFF processing pipelines -- producing usable
    corpora at the end.
    """
    from plumbum.cmd import zstdcat, zstdmt

    pipeline = add_head(zstdcat["-D", "zstd-compression-dictionary", inf], head)
    if method == "simple":
        pipeline = (
            pipeline
            | python[filter_py, "no-support", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
        )
    elif method == "complex":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "align-dom", "-", "-"]
        )
    else:
        assert False, "Unknown method"
    pipeline = pipeline | zstdmt["-D", "zstd-compression-dictionary", "-", "-o", outf]
    pipeline(retcode=[-13, 0])


@pipeline.command("unified-to-sup")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("keyin", type=click.Path(exists=True))
@click.argument("outf", type=click.Path())
@click.argument("key3out", type=click.Path())
@click.argument("keyout", type=click.Path())
def unified_to_sup(inf, keyin, outf, key3out, keyout):
    """
    Make the unified format into the senseval format used by the supervised
    systems (at least It Makes Sense) for both training and test data.
    """
    tempdir = tempfile.mkdtemp(prefix="train")
    python(munge_py, "unified-to-senseval", inf, keyin, tempdir)
    (
        python[munge_py, "senseval-gather", tempdir, outf, "-"]
        | tee[key3out]
        | python[munge_py, "unified-key-to-ims-test", "-", keyout]
    )()


@pipeline.command("unified-to-eval")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("keyin", type=click.Path(exists=True))
@click.argument("dirout", type=click.Path())
def unified_to_eval(inf, keyin, dirout):
    """
    Converts a unified corpus into all the data needed for finn-wsd-eval in a
    directory.
    """
    from stiff.eval import get_eval_paths

    if not os.path.exists(dirout):
        os.makedirs(dirout, exist_ok=True)
    root, ps = get_eval_paths(dirout)
    python(
        filter_py,
        "split",
        "--sentences",
        "1000",
        inf,
        ps["test"]["unified"],
        ps["train"]["unified"],
        keyin,
        ps["test"]["unikey"],
        ps["train"]["unikey"],
    )
    for pdict in ps.values():
        unified_to_sup.callback(
            pdict["unified"],
            pdict["unikey"],
            pdict["sup"],
            pdict["sup3key"],
            pdict["supkey"],
        )
        python(munge_py, "finnpos-senseval", pdict["sup"], pdict["suptag"])
        python(munge_py, "omorfi-segment-senseval", pdict["sup"], pdict["supseg"])


@pipeline.command("mk-stiff")
@click.argument("indir", type=click.Path(exists=True))
@click.argument("outf", type=click.Path())
def mk_stiff(indir, outf):
    """
    Make the raw, unfiltered version of STIFF.
    """
    from plumbum.cmd import zstdmt

    (
        python[tag_py, indir, "-"]
        | zstdmt["-D", "zstd-compression-dictionary", "-", "-o", outf]
    )()


@pipeline.command("man-ann-eurosense")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("outf", type=click.File("w"))
def man_ann_eurosense(inf, outf):
    (
        python[filter_py, "lang", "fi", inf, "-"]
        | python[filter_py, "rm-empty", "--text", "-", "-"]
        | python[filter_py, "sample", "-", "-"]
        | python[man_ann_py, "filter", "-", "-"]
        > outf
    )(retcode=[0, 1])


@pipeline.command("man-ann-tdt")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("outf", type=click.File("w"))
def man_ann_tdt(inf, outf):
    (
        python[man_ann_py, "conllu-gen", inf, "-"]
        | python[filter_py, "sample", "-", "-"]
        | python[man_ann_py, "filter", "-", "-"]
        > outf
    )(retcode=[0, 1])


if __name__ == "__main__":
    pipeline()
