import tempfile
import os
import sys
import click
from plumbum.cmd import cp, tee
from plumbum import local
from stiff.eval import get_eval_paths, get_partition_paths
from stiff.utils.pipeline import add_head, add_zstd, ensure_dir
from os.path import join as pjoin, samefile
from typing import List, Optional

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
    pipeline = add_head(filter_py, add_zstd(inf), head)
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
    pipeline = add_head(filter_py, add_zstd(inf), head)
    pipeline = (
        mk_eurosense2stifflike_pipeline(pipeline, babel2wn_map)
        | python[munge_py, "eurosense-to-unified", "-", "-"]
        | python[munge_py, "unified-split", "-", outf, keyout]
    )
    pipeline(retcode=[-13, 0], stderr=sys.stderr)


@pipeline.command("stiff2unified")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("outf", type=click.Path())
@click.argument("keyout", type=click.Path())
@click.option("--head", default=None)
@click.option(
    "--input-fmt",
    type=click.Choice(["man-ann-stiff", "man-ann-europarl", "stiff"]),
    default="stiff",
)
def stiff2unified(inf, outf, keyout, head, input_fmt):
    pipeline = (
        add_head(filter_py, add_zstd(inf), head)
        | python[munge_py, "stiff-select-wn", "--wn", "qf2", "-", "-"]
        | python[filter_py, "tok-span-dom", "-", "-"]
        | python[munge_py, "lemma-to-synset", "-", "-"]
        | python[munge_py, "stiff-to-unified", "--input-fmt", input_fmt, "-", "-"]
        | python[munge_py, "unified-split", "-", outf, keyout]
    )
    pipeline(retcode=[-13, 0], stderr=sys.stderr)


@pipeline.command("unified-to-sup")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("keyin", type=click.Path(exists=True))
@click.argument("outf", type=click.Path())
@click.argument("key3out", type=click.Path())
@click.argument("keyout", type=click.Path())
@click.argument("outtagf", type=click.Path(), required=False)
@click.option("--semcor/--fin")
@click.option("--exclude-word", multiple=True)
@click.option("--filter-key", type=click.Path())
def unified_to_sup(
    inf,
    keyin,
    outf,
    key3out,
    keyout,
    outtagf,
    semcor=False,
    exclude_word: Optional[List[str]] = None,
    filter_key: Optional[str] = None,
):
    """
    Make the unified format into the senseval format used by the supervised
    systems (at least It Makes Sense) for both training and test data.
    """
    if exclude_word is None:
        exclude_word = []
    tempdir = tempfile.mkdtemp(prefix="train")

    def u2s(keyin, tempdir, synset_group=False, write_tag=False):
        u2s_args = [munge_py, "unified-to-senseval", inf, keyin, tempdir]
        for ex in exclude_word:
            u2s_args.extend(["--exclude-word", ex])
        if filter_key:
            u2s_args.extend(["--filter-key", filter_key])
        if synset_group:
            u2s_args.append("--synset-group")
        if write_tag:
            u2s_args.append("--write-tag")
        python(*u2s_args)

    def gather(tempdir, outf, write_keyout=True, write_tag=False):
        args = [
            munge_py,
            "senseval-gather",
            tempdir,
            outf,
            "-" if write_keyout else "/dev/null",
        ]
        if write_tag:
            args.append("--write-tag")
        pipeline = python[args]
        if write_keyout:
            pipeline = (
                pipeline
                | tee[key3out]
                | python[munge_py, "unified-key-to-ims-test", "-", keyout]
            )
        pipeline()

    if semcor:
        # Convert key
        synsets_key = tempfile.mktemp(suffix="synsets.key")
        python(munge_py, "lemma-to-synset-key", keyin, synsets_key)

        # Write non-tagged
        u2s(synsets_key, tempdir, synset_group=True, write_tag=True)
        gather(tempdir, outf, write_keyout=True)

        # Write tagged
        gather(tempdir, outtagf, write_keyout=False, write_tag=True)
    else:
        u2s(keyin, tempdir)
        gather(tempdir, outf, write_keyout=True)


@pipeline.command("unified-auto-man-to-evals")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("ingoldf", type=click.Path(exists=True))
@click.argument("keyin", type=click.Path(exists=True))
@click.argument("goldkeyin", type=click.Path(exists=True))
@click.argument("dirout", type=click.Path())
@click.option("--rm-blacklist/--keep-blacklist")
def unified_auto_man_to_evals(inf, ingoldf, keyin, goldkeyin, dirout, rm_blacklist):
    """
    Converts a unified corpus and manually annotated data into a full full
    train/dev/test split for use by finn-wsd-eval.
    """
    ps = {}
    for seg in ["train", "devtest", "dev", "test"]:
        segoutdir = pjoin(dirout, seg)
        os.makedirs(segoutdir, exist_ok=True)
        ps[seg] = get_partition_paths(segoutdir, "corpus")
    python(
        filter_py,
        "split",
        "--sentences",
        "1000",
        inf,
        ps["devtest"]["unified"],
        ps["train"]["unified"],
        keyin,
        ps["devtest"]["unikey"],
        ps["train"]["unikey"],
    )
    python(
        filter_py,
        "unified-test-dev-split",
        ps["devtest"]["unified"],
        ingoldf,
        ps["devtest"]["unikey"],
        goldkeyin,
        ps["dev"]["unified"],
        ps["dev"]["unikey"],
    )
    cp(ingoldf, ps["test"]["unified"])
    cp(goldkeyin, ps["test"]["unikey"])
    if rm_blacklist:
        exclude = ["olla", "ei"]
    else:
        exclude = []
    for seg in ["train", "dev", "test"]:
        segoutdir = pjoin(dirout, seg)
        unified_to_single_eval.callback(
            "corpus",
            pjoin(segoutdir, "corpus.xml"),
            pjoin(segoutdir, "corpus.key"),
            segoutdir,
            exclude,
        )


@pipeline.command("unified-to-eval")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("keyin", type=click.Path(exists=True))
@click.argument("dirout", type=click.Path())
def unified_to_eval(inf, keyin, dirout):
    """
    Converts a unified corpus into all the data needed for finn-wsd-eval in a
    directory.
    """
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
    for seg in ps.key():
        unified_to_single_eval.callback(seg, inf, keyin, dirout)


@pipeline.command("unified-to-single-eval")
@click.argument("seg")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("keyin", type=click.Path(exists=True))
@click.argument("dirout", type=click.Path())
@click.argument("exclude", nargs=-1)
def unified_to_single_eval(seg, inf, keyin, dirout, exclude):
    """
    Converts a unified corpus into all the data the data needed for a single
    test/train segment by finn-wsd-eval.

    This creates a simple train/test split. For a full train/dev/test split
    including manually annotated data use unified-auto-man-to-evals.
    """
    pdict = get_partition_paths(dirout, seg)
    for src, dest in [(inf, pdict["unified"]), (keyin, pdict["unikey"])]:
        if samefile(src, dest):
            continue
        cp(src, dest)

    unified_to_sup.callback(
        pdict["unified"],
        pdict["unikey"],
        pdict["sup"],
        pdict["sup3key"],
        pdict["supkey"],
        exclude,
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


@pipeline.command("train-filter")
@click.argument("mode")
@click.argument("indir", type=click.Path(exists=True))
@click.argument("outdir", type=click.Path())
@click.argument("lemmas", type=click.Path(exists=True), required=False)
def train_filter(mode, indir, outdir, lemmas):
    filter = False
    blacklist = False
    if mode == "both":
        filter = True
        blacklist = True
    elif mode == "blacklist":
        blacklist = True
    elif mode == "filter":
        filter = True
    else:
        assert False
    for idx, fn in enumerate(
        ["corpus.sup.xml", "corpus.sup.seg.xml", "corpus.sup.tag.xml"]
    ):
        pipeline = None
        if blacklist:
            args = [munge_py, "senseval-rm-lemma", "--lemmas", "olla,ei", "-", "-"]
            if idx == 0:
                args.append(pjoin(outdir, "rm-keys.pkl"))
            pipeline = python[args]
        if filter:
            args = [munge_py, "senseval-filter-lemma", lemmas, "-", "-"]
            if idx == 0:
                args.append(pjoin(outdir, "filter-keys.pkl"))
            if pipeline is None:
                pipeline = python[args]
            else:
                pipeline |= python[args]
        ((pipeline < pjoin(indir, fn)) > pjoin(outdir, fn))()
    for cmd, pkl in ([("key-rm-lemma", "rm-keys.pkl")] if blacklist else []) + (
        [("key-filter-lemma", "filter-keys.pkl")] if filter else []
    ):
        for flag, fn in [("--two", "corpus.sup.key"), ("--three", "corpus.sup.key")]:
            python(
                munge_py,
                cmd,
                flag,
                pjoin(indir, fn),
                pjoin(outdir, fn),
                pjoin(outdir, pkl),
            )


if __name__ == "__main__":
    pipeline()
