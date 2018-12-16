from string import Template


METHOD_CODES = {
    "mono-unambg": "U",
    "mono-1st": "MR",
    "mono-unambg-finnpos-soft": "MF1",
    "mono-unambg-finnpos-hard": "MF2",
    "mono-unambg-finnpos-x-hard": "MF3",
    "finnpos-first-precision": "FP1",
    "finnpos-no-pos-first-precision": "FP2",
    "finnpos-no-pos-soft-first-precision": "FP3",
    "finnpos-no-pos-soft-deriv-first-precision": "FP4",
    "finnpos-no-pos-soft-supported-freq-first-precision": "FP5",
    "finnpos-first-recall": "FR",
    "simple-precision": "SP",
    "simple-recall": "SR",
    "high-precision": "HP",
    "high-recall": "HR",
    "balanced-recall": "BR",
    "balanced": "B",
    "balanced-precision": "BP",
    "eurosense-coverage": "EC",
    "eurosense-precision": "EP",
}

INV_METHOD_CODES = {
    short_code: long_code for long_code, short_code in METHOD_CODES.items()
}

METHODS = {
    "mono-unambg": [["rm-ambg"]],
    "mono-1st": [["freq-dom"], ["rm-ambg"]],
    "mono-unambg-finnpos-soft": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=normal"],
        ["finnpos-naive-pos-dom", "--proc=dom"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["rm-ambg"],
    ],
    "mono-unambg-finnpos-hard": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-pos-dom", "--proc=rm"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["rm-ambg"],
    ],
    "mono-unambg-finnpos-x-hard": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-pos-dom", "--proc=rm-agg"],
        ["finnpos-naive-lemma-dom", "--proc=rm"],
        ["rm-ambg"],
    ],
    "finnpos-first-precision": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-pos-dom", "--proc=rm-agg"],
        ["finnpos-naive-lemma-dom", "--proc=rm"],
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["rm-ambg"],
    ],
    "finnpos-no-pos-first-precision": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-lemma-dom", "--proc=rm"],
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["rm-ambg"],
    ],
    "finnpos-no-pos-soft-first-precision": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["rm-ambg"],
    ],
    "finnpos-no-pos-soft-deriv-first-precision": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["non-deriv-dom", "--proc=dom"],
        ["rm-ambg"],
    ],
    "finnpos-no-pos-soft-supported-freq-first-precision": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["supported-freq-dom"],
        ["rm-ambg"],
    ],
    "finnpos-first-recall": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=normal"],
        ["finnpos-naive-pos-dom", "--proc=rm-agg"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["freq-dom"],
        ["rm-ambg"],
    ],
    "simple-precision": [["has-support-dom", "--proc=rm"], ["rm-ambg"]],
    "simple-recall": [["has-support-dom", "--proc=rm"], ["freq-dom"], ["rm-ambg"]],
    "high-precision": [
        ["has-support-dom", "--proc=rm"],
        ["align-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-lemma-dom", "--proc=rm"],
        ["rm-ambg"],
    ],
    "high-recall": [
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["finnpos-naive-pos-dom", "--proc=dom"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["freq-dom"],
    ],
    "balanced-recall": [
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["finnpos-rm-pos", "--level=soft"],
        ["finnpos-naive-pos-dom", "--proc=dom"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["freq-dom"],
        ["rm-ambg"],
    ],
    "balanced": [
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["finnpos-rm-pos", "--level=normal"],
        ["finnpos-naive-pos-dom", "--proc=dom"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["freq-dom"],
        ["rm-ambg"],
    ],
    "balanced-precision": [
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["finnpos-rm-pos", "--level=normal"],
        ["finnpos-naive-pos-dom", "--proc=dom"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["rm-ambg"],
    ],
}

TREE = [
    "U",
    ["MF1", ["MF2", ["MF3", ["FP1", ["FP2", ["FP3", "FP4", "FP5"]]]]], ["FR"]],
    ["MR"],
    ["SP"],
    ["SR"],
    ["HP"],
    ["HR"],
    ["BR"],
    ["B"],
    ["BP"],
]


def get_branches(tree):
    if isinstance(tree, str):
        return [[tree]]
    elif len(tree) == 1:
        return [tree]
    head = tree[0]
    children = tree[1:]
    result = []
    for child in children:
        child_branches = get_branches(child)
        result.append([head] + child_branches[0])
        for branch in child_branches[1:]:
            result.append(branch)
    return result


DOT = Template(
    """
digraph G {
        rankdir="TB";
        graph[ranksep=0.15, nodesep=0.1];
        node[width=0.15, height=0.15, shape=none];
        edge[weight=2, arrowhead=normal];
$branches
}
"""
)


def get_dot(tree):
    branch_bits = []
    for idx, branch in enumerate(get_branches(tree)):
        branch_bits.append(f"node[group=g{idx}];")
        branch_bits.append(" -> ".join(branch) + ";")
    return DOT.substitute({"branches": "\n".join(branch_bits)})
