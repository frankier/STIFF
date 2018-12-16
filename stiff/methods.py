from string import Template


METHOD_CODES = {
    "mono-unambg": "U",
    "mono-recall": "MR",
    "mono-precision-1": "MP1",
    "mono-precision-2": "MP2",
    "mono-precision-3": "MP3",
    "bilingual-precision-1": "BP1",
    "bilingual-precision-2": "BP2",
    "bilingual-precision-3": "BP3",
    "bilingual-precision-4": "BP4",
    "simple-precision": "SP",
    "simple-recall": "SR",
    "max-precision": "MXP",
    "bilingual-recall-1": "BR1",
    "bilingual-recall-2": "BR2",
    "bilingual-recall-3": "BR3",
    "eurosense-coverage": "EC",
    "eurosense-precision": "EP",
}

INV_METHOD_CODES = {
    short_code: long_code for long_code, short_code in METHOD_CODES.items()
}

METHODS = {
    "mono-unambg": [["rm-ambg"]],
    "mono-recall": [["freq-dom"], ["rm-ambg"]],
    "mono-precision-1": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=normal"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["rm-ambg"],
    ],
    "mono-precision-2": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["rm-ambg"],
    ],
    "mono-precision-3": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-lemma-dom", "--proc=rm"],
        ["rm-ambg"],
    ],
    "bilingual-precision-1": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-lemma-dom", "--proc=rm"],
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["rm-ambg"],
    ],
    "bilingual-precision-2": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["rm-ambg"],
    ],
    "bilingual-precision-3": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["non-deriv-dom", "--proc=dom"],
        ["rm-ambg"],
    ],
    "bilingual-precision-4": [
        ["non-recurs-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["supported-freq-dom"],
        ["rm-ambg"],
    ],
    "simple-precision": [["has-support-dom", "--proc=rm"], ["rm-ambg"]],
    "simple-recall": [["has-support-dom", "--proc=rm"], ["freq-dom"], ["rm-ambg"]],
    "max-precision": [
        ["has-support-dom", "--proc=rm"],
        ["align-dom", "--proc=rm"],
        ["finnpos-rm-pos", "--level=agg"],
        ["finnpos-naive-lemma-dom", "--proc=rm"],
        ["rm-ambg"],
    ],
    "bilingual-recall-1": [
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["finnpos-naive-pos-dom", "--proc=dom"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["freq-dom"],
    ],
    "bilingual-recall-2": [
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["finnpos-rm-pos", "--level=soft"],
        ["finnpos-naive-pos-dom", "--proc=dom"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["freq-dom"],
        ["rm-ambg"],
    ],
    "bilingual-recall-3": [
        ["has-support-dom", "--proc=dom"],
        ["align-dom", "--proc=dom"],
        ["finnpos-rm-pos", "--level=normal"],
        ["finnpos-naive-pos-dom", "--proc=dom"],
        ["finnpos-naive-lemma-dom", "--proc=dom"],
        ["freq-dom"],
        ["rm-ambg"],
    ],
}

TREE = [
    "U",
    ["MP1", ["MP2", ["MP3", ["BP1", ["BP2", "BP3", "BP4"]]]]],
    ["MR", ["BR1", ["BR2", ["BR3"]]]],
    ["SP"],
    ["SR"],
    ["MXP"],
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
