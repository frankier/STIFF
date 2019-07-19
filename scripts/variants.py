import os
import sys
import click
from stiff.methods import (
    CAT_DOCS,
    INV_METHOD_CODES,
    METHOD_CODES,
    METHODS,
    STAGE_CATS,
    STAGE_DOCS,
    TREE,
    get_dot,
    get_forest,
    get_critical_nodes,
    lookup_stage,
)
from stiff.utils.pipeline import add_head, ensure_dir, exec_pipeline
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

    exec_pipeline(pipeline, retcode=[-13, 0])


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


def get_used_stages():
    return {stage for method in METHODS.values() for stage in method}


def get_cat_stages(stage_cats):
    for stage_names in stage_cats.values():
        if isinstance(stage_names, dict):
            yield from get_cat_stages(stage_names)
        else:
            yield from stage_names


def get_doc_stages():
    categorised_stages = set(get_cat_stages(STAGE_CATS))
    documented_stages = set(STAGE_DOCS.keys())
    categorised_undocumented_stages = categorised_stages - documented_stages
    if len(categorised_undocumented_stages):
        print(
            "Found the following stages which were categorised but not documented: {}".format(
                ", ".join(categorised_undocumented_stages)
            )
        )
        return
    documented_uncategorised_stages = documented_stages - categorised_stages
    if len(documented_uncategorised_stages):
        print(
            "Found the following stages which were documented but not categorised: {}".format(
                ", ".join(documented_uncategorised_stages)
            )
        )
        return
    return documented_stages


@variants.command("stages-check")
def stages_check():
    """
    Check the integrity of the stages, such as listing undocumented stages or
    documented stages which are not used.
    """
    doc_stages = get_doc_stages()
    if doc_stages is None:
        return
    replacements = []
    for stage in doc_stages:
        if "/" not in stage:
            continue
        replacements.append(stage)
    doc_stages -= set(replacements)
    new_stages = []
    for replacement in replacements:
        new_bit, old_bit = replacement.split("/")
        for stage in doc_stages:
            new_stages.append(stage.replace(old_bit, new_bit))
    doc_stages |= set(new_stages)

    used_stages = get_used_stages()
    used_undocumented_stages = used_stages - doc_stages
    if len(used_undocumented_stages):
        print(
            "Found the following stages which were used but undocumented: {}".format(
                ", ".join(used_undocumented_stages)
            )
        )
        return


def print_stage_tree(stages):
    for cat_code, stage_codes in stages.items():
        print("  \\item {}".format(CAT_DOCS[cat_code]).strip())
        print("  \\begin{itemize}")
        if isinstance(stage_codes, dict):
            print_stage_tree(stage_codes)
        else:
            for stage_code in stage_codes:
                print(
                    "    \\item \\textbf{{{}}} {}".format(
                        stage_code, STAGE_DOCS[stage_code].strip()
                    )
                )
        print("  \\end{itemize}")


@variants.command("mk-tournament-stages")
def mk_tournament_stages():
    print("\\begin{itemize}")
    print_stage_tree(STAGE_CATS)
    print("\\end{itemize}")


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
