import click
from stiff.utils.xml import transform_sentences
from stiff.utils.anns import get_ann_pos, get_ann_pos_dict
from functools import reduce
import json


@filter.command("freq-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def freq_dom(inf, outf):
    """
    Dominance filter:

    When there are multiple annotations of the exact same anchor, (position +
    content) keep only the one with the highest count, breaking ties with alphabetical-ness.
    """

    def sent_freq_dom(sent):
        anns = sent.xpath("./annotations/annotation")
        ann_index = {}
        for ann in anns:
            tok, tok_len = get_ann_pos(ann)
            anchor = ann.attrib["anchor"]
            ann_index.setdefault((anchor, tok, tok_len), []).append(ann)
        for cand_anns in ann_index.values():
            ranked_anns = sorted(
                (
                    (int(cand_ann.attrib["rank"]), cand_ann.text, cand_ann)
                    for cand_ann in cand_anns
                )
            )
            best_ann = ranked_anns[0]
            for cand_ann in cand_anns:
                if cand_ann != best_ann:
                    cand_ann.getparent().remove(cand_ann)

    transform_sentences(inf, sent_freq_dom, outf)


def greedy_max_span(positions):
    max_pos = 0
    for pos in positions:
        positions[pos].sort(reverse=True)
        if pos > max_pos:
            max_pos = pos
    anns = []
    cur_pos = 0
    while cur_pos <= max_pos:
        while cur_pos not in positions:
            cur_pos += 1
        cur_len, ann = positions[cur_pos][0]
        anns.append(ann)
        cur_pos += cur_len
    return anns


def trim_anns(anns, new_anns):
    for ann in anns:
        if ann not in new_anns:
            ann.getparent().remove(ann)


@filter.command("tok-span-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def tok_span_dom(inf, outf):
    """
    Dominance filter:

    When one annotation's multi-token anchor spans (contains) another, keep the
    one with the longest token span. When there is a partial overlap (none
    dominates), proceed greedily.
    """

    def sent_span_dom(sent):
        anns = sent.xpath("./annotations/annotation")
        token_positions = {}
        for ann in anns:
            tok, tok_len = get_ann_pos(ann)
            token_positions.setdefault(tok, []).append((tok_len, ann))
        new_anns = greedy_max_span(token_positions)
        trim_anns(anns, new_anns)

    transform_sentences(inf, sent_span_dom, outf)


@filter.command("char-span-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def char_span_dom(inf, outf):
    """
    Dominance filter:

    When one annotation's single-token anchor spans (contains) another, keep
    the one with the longest character span. When there is a partial overlap
    (none dominates), proceed greedily.
    """

    def sent_span_dom(sent):
        anns = sent.xpath("./annotations/annotation")
        tokens = {}
        for ann in anns:
            tok, tok_len = get_ann_pos(ann)
            if tok_len == 1:
                tokens.setdefault(tok, []).append(ann)
        for tok, anns in tokens.items():
            char_positions = {}
            for ann in anns:
                anchor_pos = get_ann_pos_dict(ann)
                anchor = ann.attrib["anchor"]
                char_positions.setdefault(anchor_pos["char"], []).append(
                    (len(anchor), ann)
                )
        new_anns = greedy_max_span(char_positions)
        trim_anns(anns, new_anns)

    transform_sentences(inf, sent_span_dom, outf)


def get_wn_pos(ann):
    wn_ids = ann.text.split(" ")
    poses = [wn_id.split(".")[1] for wn_id in wn_ids]
    assert reduce(lambda a, b: a == b, poses)
    return "a" if poses[0] == "s" else poses[0]


def get_headword_offset(ann):
    """
    How to deal with multiwords? Could consider only the headword. Usually the
    last word is the headword? Or maybe last is headword for noun first for
    verb?
    """
    pos = get_wn_pos(ann)
    if pos == "v":
        return 0
    else:
        # "n" "r" "a"
        tok, tok_len = get_ann_pos(ann)
        return tok_len - 1


FINNPOS_WN_POS_MAP = {"VERB": "v", "NOUN": "n", "ADVERB": "r", "ADJECTIVE": "a"}


def lemmatized_pos_match(wn_pos, finnpos_feats):
    finnpos_pos = finnpos_feats["pos"]
    finnpos_wn_pos = FINNPOS_WN_POS_MAP.get(finnpos_pos)
    if finnpos_wn_pos is None:
        return 0
    elif finnpos_wn_pos == wn_pos:
        return 1
    else:
        return -1


@filter.command("finnpos-naive-lemma-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--proc", type=click.Choice(["dom", "rm"]))
def finnpos_naive_lemma_dom(inf, outf, proc):
    """
    FinnPOS Dominance filter: Use FinnPOS annotations to support certain
    annotations over others, in terms of POS or lemma.

    Naive lemma filter: Based on matching exactly the lemma. Either as
    requirement or dominance filter.
    """

    def sent_naive_lemma_dom(sent):
        gram = sent.xpath("gram[type=finnpos]")
        finnpos_analys = json.loads(gram.text)
        assert len(gram) == 1
        anns = sent.xpath("./annotations/annotation")
        new_anns = anns.copy()
        best_anns = {}
        for ann in anns:
            tok, tok_len = get_ann_pos(ann)
            head_off = get_headword_offset(ann)
            lemma, feats = finnpos_analys[tok + head_off]
            wn_lemma = ann.attrib["wnlemma"].split("_")[head_off]
            if lemma == wn_lemma:
                if proc == "dom":
                    best_anns.setdefault((tok, tok_len), []).append(ann)
            elif proc == "rm":
                new_anns.remove(ann)
        if proc == "dom":
            for ann in anns:
                tok, tok_len = get_ann_pos(ann)
                if ann not in best_anns[(tok, tok_len)]:
                    new_anns.remove(ann)
        trim_anns(anns, new_anns)

    transform_sentences(inf, sent_naive_lemma_dom, outf)


@filter.command("finnpos-naive-pos-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--proc", type=click.Choice(["dom", "rm-dom", "rm", "rm-agg"]))
def finnpos_naive_pos_dom(inf, outf, proc):
    """
    FinnPOS Dominance filter: Use FinnPOS annotations to support certain
    annotations over others, in terms of POS or lemma.

    Heuristic POS removal: Remove specific POSs altogether. Most commonly
    PRONOUN, since this POS never exists in WordNet.
    """
    if proc == "dom":
        rm_ranks = []
        do_dom = True
    elif proc == "rm-dom":
        rm_ranks = [-1]
        do_dom = True
    elif proc == "rm":
        rm_ranks = [-1]
        do_dom = False
    elif proc == "rm-agg":
        rm_ranks = [-1, 0]
        do_dom = False

    def sent_naive_pos_dom(sent):
        gram = sent.xpath("gram[type=finnpos]")
        finnpos_analys = json.loads(gram.text)
        assert len(gram) == 1
        anns = sent.xpath("./annotations/annotation")
        new_anns = anns.copy()
        best_ranks = {}
        ranks = {}
        for ann in anns:
            tok, tok_len = get_ann_pos(ann)
            wn_pos = get_wn_pos(ann)
            head_off = get_headword_offset(ann)
            lemma, feats = finnpos_analys[tok + head_off]
            rank = lemmatized_pos_match(wn_pos, feats)
            ranks[ann] = rank
            if rank in rm_ranks:
                new_anns.remove(ann)
            elif do_dom:
                if rank > best_ranks[(tok, tok_len)]:
                    best_ranks[(tok, tok_len)] = rank
        if do_dom:
            for ann in anns:
                tok, tok_len = get_ann_pos(ann)
                best_rank = best_ranks[(tok, tok_len)]
                if best_rank > ranks[ann]:
                    new_anns.remove(ann)
        trim_anns(anns, new_anns)

    transform_sentences(inf, sent_naive_pos_dom, outf)
