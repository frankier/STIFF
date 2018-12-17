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


def normalise_tree(tree):
    for idx in range(1, len(tree)):
        child = tree[idx]
        if isinstance(child, str):
            tree[idx] = [child]
        else:
            normalise_tree(child)


normalise_tree(TREE)


def get_branches(tree):
    if len(tree) == 1:
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
    critical_nodes = get_critical_nodes(tree)
    branch_bits = []
    for idx, branch in enumerate(get_branches(tree)):
        branch_bits.append(f"node[group=g{idx}];")
        for idx in range(0, len(branch) - 1):
            parent = branch[idx]
            child = branch[idx + 1]
            diff = get_disp_diff(parent, child)
            if diff and not (parent in critical_nodes and child in critical_nodes):
                branch_bits.append('{} -> {}[xlabel="{}"];'.format(parent, child, diff))
            else:
                branch_bits.append("{} -> {};".format(parent, child))
    return DOT.substitute({"branches": "\n".join(branch_bits)})


FOREST = Template(
    r"""
\begin{forest}
  for tree={
    font=\ttfamily,
    grow'=0,
    child anchor=west,
    parent anchor=south,
    anchor=west,
    calign=first,
    edge path={
      \noexpand\path [draw, \forestoption{edge}]
      (!u.south west) +(7.5pt,0) |- node[fill,inner sep=1.25pt] {} (.child anchor)\forestoption{edge label};
    },
    before typesetting nodes={
      if n=1
        {insert before={[,phantom]}}
        {}
    },
    fit=band,
    before computing xy={l=15pt},
  }
$tree
\end{forest}
"""
)


def get_forest(tree):
    def draw_node(node, parent=None):
        head = node[0]
        children = node[1:]
        diff = get_disp_diff(parent, head)
        if diff:
            comment = "\t" + diff
        else:
            comment = ""
        return "[{{{}{}}}\n{}]".format(
            head, comment, " ".join((draw_node(child, head) for child in children))
        )

    return FOREST.substitute({"tree": draw_node(tree)})


def get_stages(short_code):
    return METHODS[INV_METHOD_CODES[short_code]]


def get_list_ancestor(diff_tree):
    if isinstance(diff_tree.t2, list):
        return diff_tree
    return get_list_ancestor(diff_tree.up)


def get_disp_diff(parent, child):
    from jsondiff import diff, insert

    if parent is None:
        return

    parent_stages = get_stages(parent)
    child_stages = get_stages(child)
    diffed = diff(parent_stages, child_stages)
    keys_list = list(diffed.keys())
    if len(keys_list) != 1:
        return
    key = keys_list[0]
    if key == insert:
        inserts = diffed[key]
        if len(inserts) != 1:
            return
        return "+ {}".format(" ".join(inserts[0][1]))
    elif isinstance(key, int):
        return "{} / {}".format(
            " ".join(child_stages[key]), " ".join(parent_stages[key])
        )
    else:
        return


def get_critical_nodes(tree, parent=None):
    result = set()
    head = tree[0]
    children = tree[1:]
    diff = get_disp_diff(parent, head) if parent is not None else None
    if diff is None or not children:
        result.add(head)
    for child in children:
        result.update(get_critical_nodes(child, head))
    return result
