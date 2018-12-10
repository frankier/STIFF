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


def ensure_dir(dirout):
    if not os.path.exists(dirout):
        os.makedirs(dirout, exist_ok=True)


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
@click.option("--no-zstd-out/--zstd-out")
def proc_stiff(method, inf, outf, head=None, no_zstd_out=False):
    """
    Do one of several standard STIFF processing pipelines -- producing usable
    corpora at the end.
    """
    from plumbum.cmd import zstdcat, zstdmt

    if os.environ.get("TRACE_PIPELINE"):
        print(method)
    pipeline = add_head(zstdcat["-D", "zstd-compression-dictionary", inf], head)
    if method == "none":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
        )
    elif method == "mono-1st-break":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "freq-dom", "--break-ties", "-", "-"]
        )
    elif method == "mono-1st":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "freq-dom", "-", "-"]
            | python[filter_py, "rm-ambg", "-", "-"]
        )
    elif method == "mono-unambg":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "rm-ambg", "-", "-"]
        )
    elif method == "mono-unambg-finnpos-soft":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "non-recurs-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "finnpos-rm-pos", "--level=normal", "-", "-"]
            | python[filter_py, "finnpos-naive-pos-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "finnpos-naive-lemma-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "rm-ambg", "-", "-"]
        )
    elif method == "mono-unambg-finnpos-hard":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "non-recurs-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "finnpos-rm-pos", "--level=agg", "-", "-"]
            | python[filter_py, "finnpos-naive-pos-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "finnpos-naive-lemma-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "rm-ambg", "-", "-"]
        )
    elif method == "mono-unambg-finnpos-x-hard":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "non-recurs-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "finnpos-rm-pos", "--level=agg", "-", "-"]
            | python[filter_py, "finnpos-naive-pos-dom", "--proc=rm-agg", "-", "-"]
            | python[filter_py, "finnpos-naive-lemma-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "rm-ambg", "-", "-"]
        )
    elif method == "finnpos-first-precision":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "non-recurs-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "finnpos-rm-pos", "--level=agg", "-", "-"]
            | python[filter_py, "finnpos-naive-pos-dom", "--proc=rm-agg", "-", "-"]
            | python[filter_py, "finnpos-naive-lemma-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "has-support-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "align-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "rm-ambg", "-", "-"]
        )
    elif method == "finnpos-first-recall":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "non-recurs-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "finnpos-rm-pos", "--level=agg", "-", "-"]
            | python[filter_py, "finnpos-naive-pos-dom", "--proc=rm-agg", "-", "-"]
            | python[filter_py, "finnpos-naive-lemma-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "has-support-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "align-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "freq-dom", "-", "-"]
        )
    elif method == "simple-precision":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "has-support-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "rm-ambg", "-", "-"]
        )
    elif method == "simple-recall":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "has-support-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "freq-dom", "-", "-"]
            | python[filter_py, "rm-ambg", "-", "-"]
        )
    elif method == "simple-x-recall":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "has-support-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "freq-dom", "--break-ties", "-", "-"]
        )
    elif method == "high-precision":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "has-support-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "align-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "finnpos-rm-pos", "--level=agg", "-", "-"]
            | python[filter_py, "finnpos-naive-lemma-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "finnpos-naive-pos-dom", "--proc=rm", "-", "-"]
            | python[filter_py, "rm-ambg", "-", "-"]
        )
    elif method == "high-recall":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "has-support-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "align-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "finnpos-naive-pos-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "finnpos-naive-lemma-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "freq-dom", "-", "-"]
        )
    elif method == "balanced-recall":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "has-support-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "align-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "finnpos-rm-pos", "--level=soft", "-", "-"]
            | python[filter_py, "finnpos-naive-pos-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "finnpos-naive-lemma-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "freq-dom", "-", "-"]
            | python[filter_py, "rm-ambg", "-", "-"]
        )
    elif method == "balanced":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "has-support-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "align-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "finnpos-rm-pos", "--level=normal", "-", "-"]
            | python[filter_py, "finnpos-naive-pos-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "finnpos-naive-lemma-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "freq-dom", "-", "-"]
            | python[filter_py, "rm-ambg", "-", "-"]
        )
    elif method == "balanced-precision":
        pipeline = (
            pipeline
            | python[filter_py, "fold-support", "fi", "-", "-"]
            | python[filter_py, "lang", "fi", "-", "-"]
            | python[filter_py, "has-support-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "align-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "finnpos-rm-pos", "--level=normal", "-", "-"]
            | python[filter_py, "finnpos-naive-pos-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "finnpos-naive-lemma-dom", "--proc=dom", "-", "-"]
            | python[filter_py, "rm-ambg", "-", "-"]
        )
    else:
        assert False, "Unknown method"
    if not no_zstd_out:
        pipeline = (
            pipeline | zstdmt["-D", "zstd-compression-dictionary", "-", "-o", outf]
        )
    else:
        pipeline = pipeline > outf
    if os.environ.get("TRACE_PIPELINE"):
        print(pipeline)
    pipeline(retcode=[-13, 0])


@pipeline.command("proc-stiff-to-eval")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("dirout", type=click.Path())
def proc_stiff_to_eval(inf, dirout):
    ensure_dir(dirout)
    for method in (
        "mono-1st-break",
        "mono-1st",
        "mono-unambg",
        "mono-unambg-finnpos-soft",
        "mono-unambg-finnpos-hard",
        "mono-unambg-finnpos-x-hard",
        "finnpos-first-precision",
        "finnpos-first-recall",
        "simple-precision",
        "simple-recall",
        "simple-x-recall",
        "high-precision",
        "high-recall",
        "balanced-precision",
        "balanced-recall",
        "balanced",
    ):
        proc_stiff.callback(
            method, inf, os.path.join(dirout, f"{method}.xml"), "1000", True
        )


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
