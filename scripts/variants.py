import os
import sys
import click
from stiff.methods import (
    INV_METHOD_CODES,
    METHOD_CODES,
    METHODS,
    TREE,
    get_dot,
    get_forest,
    get_critical_nodes,
    lookup_stage,
)
from stiff.utils.pipeline import add_head, ensure_dir
from plumbum import local
from string import Template

python = local[sys.executable]

dir = os.path.dirname(os.path.realpath(__file__))
filter_py = os.path.join(dir, "filter.py")


@click.group()
def variants():
    """
    These variants filter STIFF in different ways.
    """
    pass


@variants.command("proc")
@click.argument("method")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("outf", type=click.Path())
@click.option("--head", default=None)
@click.option("--no-zstd-out/--zstd-out")
def proc(method, inf, outf, head=None, no_zstd_out=False):
    from plumbum.cmd import zstdcat, zstdmt

    if os.environ.get("TRACE_PIPELINE"):
        print(method)
    pipeline = add_head(
        filter_py, zstdcat["-D", "zstd-compression-dictionary", inf], head
    )

    pipeline = (
        pipeline
        | python[filter_py, "fold-support", "fi", "-", "-"]
        | python[filter_py, "lang", "fi", "-", "-"]
    )

    method_stages = METHODS[method]
    for stage in method_stages:
        long_stage = lookup_stage(stage)
        args = [filter_py] + long_stage.split(" ") + ["-", "-"]
        pipeline = pipeline | python[args]

    if not no_zstd_out:
        pipeline = (
            pipeline | zstdmt["-D", "zstd-compression-dictionary", "-", "-o", outf]
        )
    else:
        pipeline = pipeline > outf
    if os.environ.get("TRACE_PIPELINE"):
        print(pipeline)
    pipeline(retcode=[-13, 0])


@variants.command("eval")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("dirout", type=click.Path())
def eval(inf, dirout):
    ensure_dir(dirout)
    for long_code in METHODS:
        short_code = METHOD_CODES[long_code]
        proc.callback(
            long_code, inf, os.path.join(dirout, f"{short_code}.xml"), "1000", True
        )


@variants.command("draw-tree")
@click.option("--dot/--no-dot")
def draw_tree(dot):
    if dot:
        print(get_dot(TREE))
    else:
        print(get_forest(TREE))


@variants.command("mk-correspondance-table")
def mk_correspondance_table():
    print("\\begin{tabular}{ l | l }")
    for long_name, short_name in METHOD_CODES.items():
        print(f"{short_name} & {long_name} \\\\")
    print("\\end{tabular}")


@variants.command("mk-code-boxes")
def mk_code_boxes():
    print("\\begin{multicols}{3}")
    for method_code in get_critical_nodes(TREE):
        long_method_code = INV_METHOD_CODES[method_code]
        stages = METHODS[long_method_code]
        print("\\begin{framed}")
        print("\\textbf{" + long_method_code + "}")
        for stage in stages:
            print(stage)
        print("\\end{framed}")
    print("\\end{multicols}")


FOREST_BEGIN = """
\\forestset{default preamble={
for tree={edge={->},align=center,l sep=0,inner ysep=0}
}}
"""


FOREST_PIPES = Template(
    """
\\begin{forest}
[{\\textbf{$title:}}
$tree]
\\end{forest}
"""
)


@variants.command("mk-code-pipes")
def mk_code_pipes():
    critical_nodes = get_critical_nodes(TREE)

    lengths = []
    for method_code in critical_nodes:
        long_method_code = INV_METHOD_CODES[method_code]
        stages = METHODS[long_method_code]
        lengths.append(len(stages))

    longest_node = max(lengths)
    bins = []

    def new_bin():
        bins.append({"filled": 0, "contents": []})

    unplaced = list(zip(critical_nodes, lengths))
    while unplaced:
        new_bin()
        to_remove = []
        for idx, (method_code, length) in enumerate(unplaced):
            if length + bins[-1]["filled"] <= longest_node:
                bins[-1]["filled"] += length
                bins[-1]["contents"].append(method_code)
                to_remove.append(idx)
        for idx in reversed(to_remove):
            del unplaced[idx]

    def draw_node(stages, root=True):
        if not stages:
            return ""
        return "[{{{}}}{} {}]".format(
            stages[0], ",no edge,l=0" if root else "", draw_node(stages[1:], False)
        )

    print(FOREST_BEGIN.strip())

    for bin in bins:
        print("\\begin{adjustbox}{varwidth=3cm,valign=t}")
        print("\\centering")
        for idx, method_code in enumerate(bin["contents"]):
            if idx != 0:
                print("{\\vskip 1em}")
            long_method_code = INV_METHOD_CODES[method_code]
            stages = METHODS[long_method_code]
            print(
                FOREST_PIPES.substitute(
                    {"title": method_code, "tree": draw_node(stages)}
                ).strip()
            )
        print("\\end{adjustbox}")


if __name__ == "__main__":
    variants()
