from string import Template


METHOD_CODES = {
    "null": "N",
    "mono-unambg": "U",
    "mono-recall": "MR",
    "mono-precision-1": "MP1",
    "mono-precision-2": "MP2",
    "mono-precision-3": "MP3",
    "bilingual-precision-1": "BP1",
    "bilingual-precision-2": "BP2",
    "bilingual-precision-3": "BP3",
    "bilingual-precision-3a": "BP3A",
    "bilingual-precision-4": "BP4",
    "bilingual-precision-5": "BP5",
    "simple-precision": "SP",
    "simple-recall": "SR",
    "max-precision": "MXP",
    "bilingual-recall-1": "BR1",
    "bilingual-recall-2": "BR2",
    "bilingual-recall-3": "BR3",
    "bilingual-recall-4": "BR4",
    "eurosense-coverage": "EC",
    "eurosense-precision": "EP",
}

INV_METHOD_CODES = {
    short_code: long_code for long_code, short_code in METHOD_CODES.items()
}

STAGE_CODES = {
    "pos-dom": "finnpos-naive-pos-dom --proc=dom",
    "lemma-dom": "finnpos-naive-lemma-dom --proc=dom",
    "lemma-rm": "finnpos-naive-lemma-dom --proc=rm",
    "rm-pos-soft": "finnpos-rm-pos --level=soft",
    "rm-pos-norm": "finnpos-rm-pos --level=normal",
    "rm-pos-agg": "finnpos-rm-pos --level=agg",
    "recurs-rm": "non-recurs-dom --proc=rm",
    "wiki-src-dom": "non-wiki-src --proc=dom",
    "wiki-trg-dom": "non-wiki-trg --proc=dom",
    "wiki-src-sup": "supported-non-wiki-src",
    "align-dom": "align-dom --proc=dom",
    "align-rm": "align-dom --proc=rm",
    "deriv-dom": "non-deriv-dom --proc=dom",
    "sup-dom": "has-support-dom --proc=dom",
    "sup-rm": "has-support-dom --proc=rm",
    "sup-freq-dom": "supported-freq-dom",
    "src-len-dom": "src-char-len-dom",
    "src-span-dom": "src-char-span-dom",
    "span-dom-sup": "tok-span-dom --sup-only",
}


def lookup_stage(stage):
    if stage in STAGE_CODES:
        return STAGE_CODES[stage]
    else:
        return stage


METHODS = {
    "null": [],
    "mono-unambg": ["rm-ambg"],
    "mono-recall": ["freq-dom", "rm-ambg"],
    "mono-precision-1": ["recurs-rm", "rm-pos-norm", "lemma-dom", "rm-ambg"],
    "mono-precision-2": ["recurs-rm", "rm-pos-agg", "lemma-dom", "rm-ambg"],
    "mono-precision-3": ["recurs-rm", "rm-pos-agg", "lemma-rm", "rm-ambg"],
    "bilingual-precision-1": [
        "recurs-rm",
        "rm-pos-agg",
        "lemma-rm",
        "sup-dom",
        "rm-ambg",
    ],
    "bilingual-precision-2": [
        "recurs-rm",
        "rm-pos-agg",
        "lemma-rm",
        "sup-dom",
        "align-dom",
        "rm-ambg",
    ],
    "bilingual-precision-3": [
        "recurs-rm",
        "rm-pos-agg",
        "lemma-rm",
        "sup-dom",
        "align-dom",
        "deriv-dom",
        "rm-ambg",
    ],
    "bilingual-precision-3a": [
        "recurs-rm",
        "rm-pos-agg",
        "lemma-rm",
        "sup-dom",
        "align-dom",
        "sup-freq-dom",
        "rm-ambg",
    ],
    "bilingual-precision-4": [
        "recurs-rm",
        "rm-pos-agg",
        "lemma-rm",
        "sup-dom",
        "align-dom",
        "sup-freq-dom",
        "wiki-trg-dom",
        "rm-ambg",
    ],
    "bilingual-precision-5": [
        "recurs-rm",
        "rm-pos-agg",
        "lemma-rm",
        "sup-dom",
        "align-dom",
        "deriv-dom",
        "src-span-dom",
        "sup-freq-dom",
        "wiki-trg-dom",
        "hyp-dom",
        "rm-ambg",
    ],
    "simple-precision": ["sup-rm", "rm-ambg"],
    "simple-recall": ["sup-rm", "freq-dom", "rm-ambg"],
    "max-precision": ["sup-rm", "align-rm", "rm-pos-agg", "lemma-rm", "rm-ambg"],
    "bilingual-recall-1": [
        "sup-dom",
        "align-dom",
        "pos-dom",
        "lemma-dom",
        "freq-dom",
        "rm-ambg",
    ],
    "bilingual-recall-2": [
        "sup-dom",
        "align-dom",
        "rm-pos-soft",
        "pos-dom",
        "lemma-dom",
        "freq-dom",
        "rm-ambg",
    ],
    "bilingual-recall-3": [
        "sup-dom",
        "align-dom",
        "rm-pos-norm",
        "pos-dom",
        "lemma-dom",
        "freq-dom",
        "rm-ambg",
    ],
    "bilingual-recall-4": [
        "sup-dom",
        "align-dom",
        "rm-pos-agg",
        "pos-dom",
        "lemma-dom",
        "freq-dom",
        "rm-ambg",
    ],
}

TREE = [
    "U",
    ["MP1", ["MP2", ["MP3", ["BP1", ["BP2", "BP3", ["BP3A", ["BP4", ["BP5"]]]]]]]],
    ["MR", ["BR1", ["BR2", ["BR3", ["BR4"]]]]],
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
            comment = " {\\hskip 1em} " + diff
        else:
            comment = ""
        return "[{{\\textbf{{{}}}{}}}\n{}]".format(
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
    from jsondiff import diff, insert, delete

    if parent is None:
        return

    parent_stages = get_stages(parent)
    child_stages = get_stages(child)
    diffed = diff(parent_stages, child_stages)
    keys_set = set(diffed.keys())
    if keys_set == {insert}:
        inserts = diffed[insert]
        if len(inserts) != 1:
            return
        return "+{}".format(inserts[0][1])
    elif keys_set == {insert, delete}:
        inserts = diffed[insert]
        deletes = diffed[delete]
        if len(inserts) != 1 or len(deletes) != 1:
            return
        return "{} / {}".format(inserts[0][1], parent_stages[deletes[0]])
    else:
        return


def get_critical_nodes(tree, parent=None):
    result = []
    head = tree[0]
    children = tree[1:]
    diff = get_disp_diff(parent, head) if parent is not None else None
    if diff is None or not children:
        result.append(head)
    for child in children:
        for crit_node in get_critical_nodes(child, head):
            if crit_node not in result:
                result.append(crit_node)
    return result
