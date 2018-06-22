import os
import sys
import click
from plumbum import local
from plumbum.cmd import java, python
from stiff.filter_utils import iter_sentences
from stiff.data import UNI_POS_WN_MAP

ukb_wsd = local[local.env["UKB_PATH"] + "/ukb_wsd"]

DICTABLE_OPTS = [("--ppr_w2w",), ("--ppr",), ("--dgraph_dfs", "--dgraph_rank", "ppr")]
VARIANTS = []
for extra in [(), ("--nodict_weight",)]:
    for opt in DICTABLE_OPTS:
        VARIANTS.append(opt + extra)
VARIANTS.append(("--static",))


@click.group()
def ukb():
    pass


@ukb.command()
@click.argument("input_fn")
@click.argument("graph_fn")
@click.argument("dict_fn")
@click.argument("true_tag")
def run_all(input_fn, graph_fn, dict_fn, true_tag):
    os.makedirs("guess", exist_ok=True)
    for idx, variant in enumerate(VARIANTS):
        args = variant + ("-D", dict_fn, "-K", graph_fn, "-")
        variant_fn = "guess/var{}.key".format(idx)
        pred_pipeline = (
            python[sys.argv[0], "unified_to_ukb", input_fn, "-"]
            | ukb_wsd[args]
            | python[sys.argv[0], "clean_keyfile", "-", "-"]
            > variant_fn
        )
        print(pred_pipeline)
        pred_pipeline(stderr=sys.stderr)
        eval_pipeline = java["Scorer", true_tag, variant_fn]
        print(eval_pipeline)
        eval_pipeline(stdout=sys.stdout)


@ukb.command()
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("w"))
def unified_to_ukb(inf, outf):
    for sent_elem in iter_sentences(inf):
        bits = []
        outf.write(sent_elem.attrib["id"])
        outf.write("\n")
        for instance in sent_elem.xpath("instance"):
            id = instance.attrib["id"]
            lemma = instance.attrib["lemma"]
            pos = UNI_POS_WN_MAP[instance.attrib["pos"]]
            bits.append(f"{lemma}#{pos}#{id}#1")
        outf.write(" ".join(bits))
        outf.write("\n")


@ukb.command()
@click.argument("keyin", type=click.File("r"))
@click.argument("keyout", type=click.File("w"))
def clean_keyfile(keyin, keyout):
    for line in keyin:
        bits = line.split()
        inst_id = bits[1]
        ids = bits[2:-2]
        keyout.write(inst_id)
        keyout.write(" ")
        keyout.write(" ".join(ids))
        keyout.write("\n")


if __name__ == "__main__":
    ukb()
