import tempfile
import os
import sys
import click
from plumbum.cmd import cat, tee
from plumbum import local
from stiff.utils.pipeline import add_head, ensure_dir
from os.path import join as pjoin

python = local[sys.executable]

dir = os.path.dirname(os.path.realpath(__file__))
filter_py = pjoin(dir, "filter.py")
munge_py = pjoin(dir, "munge.py")
tag_py = pjoin(dir, "tag.py")
man_ann_py = pjoin(dir, "man_ann.py")


@click.group()
def pipeline():
    """
    These pipelines compose serveral filters and munges to convert between
    formats and filter STIFF.
    """
    pass


def mk_eurosense2stifflike_pipeline(pipeline, babel2wn_map):
    tmp_dir = os.environ.get("EUROSENSE_PIPELINE_TMPDIR")
    pipeline = pipeline | python[filter_py, "lang", "fi", "-", "-"]
    if tmp_dir is not None:
        pipeline = pipeline | tee["-", pjoin(tmp_dir, "lang.fi.xml")]
    pipeline = pipeline | python[munge_py, "babelnet-lookup", "-", babel2wn_map, "-"]
    if tmp_dir is not None:
        pipeline = pipeline | tee["-", pjoin(tmp_dir, "wordnet.looked.up.xml")]
    pipeline = pipeline | python[munge_py, "eurosense-reanchor", "-", "-"]
    if tmp_dir is not None:
        pipeline = pipeline | tee["-", pjoin(tmp_dir, "reanchored.xml")]
    pipeline = (
        pipeline | python[munge_py, "eurosense-lemma-fix", "--drop-unknown", "-", "-"]
    )
    if tmp_dir is not None:
        pipeline = pipeline | tee["-", pjoin(tmp_dir, "lemma-fixed.xml")]
    pipeline = pipeline | python[filter_py, "rm-empty", "-", "-"]
    return pipeline


@pipeline.command("eurosense2stifflike")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("outf", type=click.Path())
@click.option("--head", default=None)
@click.option("--babel2wn-map", envvar="BABEL2WN_MAP", required=True)
def eurosense2stifflike(inf, outf, head, babel2wn_map):
    pipeline = add_head(filter_py, cat[inf], head)
    pipeline = (
        mk_eurosense2stifflike_pipeline(pipeline, babel2wn_map)
        | python[munge_py, "eurosense-add-anchor-positions", "-", outf]
    )
    print(pipeline)
    pipeline(retcode=[-13, 0], stderr=sys.stderr)


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
    pipeline = add_head(filter_py, cat[inf], head)
    pipeline = (
        mk_eurosense2stifflike_pipeline(pipeline, babel2wn_map)
        | python[munge_py, "eurosense-to-unified", "-", "-"]
        | python[munge_py, "unified-split", "-", outf, keyout]
    )
    pipeline(retcode=[-13, 0], stderr=sys.stderr)


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

    ensure_dir(dirout)
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
