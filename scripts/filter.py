from lxml import etree
import click
from stiff.utils.xml import (
    fixup_missing_text,
    transform_sentences,
    write_event,
    BYPASS,
    BREAK,
    free_elem,
    close_all,
)
from stiff.data.constants import DEFAULT_SAMPLE_LINES, DEFAULT_SAMPLE_MAX
from stiff.utils.anns import get_ann_pos, get_ann_pos_dict
from urllib.parse import parse_qs, urlencode
from functools import reduce
import json


@click.group()
def filter():
    """
    Filter the master STIFF corpus to produce less ambiguous or unambiguous
    versions.
    """
    pass


@filter.command("no-support")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def filter_support(inf, outf):
    """
    Remove annotations without any support at all.
    """

    def remove_no_support(elem):
        for ann in elem.xpath("./annotations/annotation"):
            if "support" in ann.attrib and ann.attrib["support"]:
                continue
            ann.getparent().remove(ann)

    transform_sentences(inf, remove_no_support, outf)


@filter.command("lang")
@click.argument("lang")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def filter_lang(lang, inf, outf):
    """
    Change a multilingual corpus to a monolingual one by selecting a single
    language.
    """

    def remove_other_langs(elem):
        for ann in elem.xpath("./annotations/annotation | ./text"):
            if ann.attrib["lang"] == lang:
                continue
            ann.getparent().remove(ann)

    transform_sentences(inf, remove_other_langs, outf)


@filter.command("fold-support")
@click.argument("lang")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def fold_support(lang, inf, outf):
    """
    Move information about how an annotation is connected to a wordnet how it
    is anchored into annotations which it supports in LANG.
    """

    def tran(elem):
        xpath = "./annotations/annotation[@lang='{}']".format(lang)
        for ann in elem.xpath(xpath):
            support = ann.attrib.get("support")
            if not support:
                continue
            new_support = []
            for supp in support.split(" "):
                supp = parse_qs(supp)
                trans_from = supp["transfer-from"][0]
                from_elem = elem.xpath(
                    "./annotations/annotation[@id='{}']".format(trans_from)
                )[0]
                from_wordnets = from_elem.attrib["wordnets"]
                for position in from_elem.attrib["anchor-positions"].split(" "):
                    from_anchor = parse_qs(position)
                    from_source = from_anchor["from-id"]
                from_lemma_path = from_elem.attrib["lemma-path"]
                del supp["transfer-from"]
                supp.update(
                    {
                        "transfer-from-wordnets": from_wordnets,
                        "transfer-from-source": from_source,
                        "transfer-from-lemma-path": from_lemma_path,
                    }
                )
                new_support.append(urlencode(supp))
            ann.attrib["support"] = " ".join(new_support)

    transform_sentences(inf, tran, outf)


@filter.command("rm-empty")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--text/--annotations")
def rm_empty(inf, outf, text):
    """
    Remove sentences with no annotations, or optionally with no text instead.
    """

    def remove_empty(elem):
        if (
            len(elem.xpath("./text")) == 0
            if text
            else len(elem.xpath("./annotations/annotation")) == 0
        ):
            return BYPASS

    transform_sentences(inf, remove_empty, outf)


@filter.command("align-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def filter_align_dom(inf, outf):
    """
    Dominance filter:

    Remove annotations which are based on unaligned transfers when there is an
    annotation based on aligned transfers of the same token.
    """

    def remove_dom_transfer(sent):
        anns = sent.xpath(
            './annotations/annotation[starts-with(@support, "aligned-transfer:")]]'
        )
        for ann in anns:
            dominated = sent.xpath(
                (
                    './annotations/annotation[starts-with(@support, "transfer:")]'
                    '[@anchor-positions="{}"]'
                ).format(ann["anchor-positions"])
            )
            for dom in dominated:
                dom.getparent().remove(dom)

    transform_sentences(inf, remove_dom_transfer, outf)


@filter.command("head")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--sentences", default=100)
def head(inf, outf, sentences):
    """
    Take the first SENTENCES sentences from INF.
    """
    seen_sents = 0

    def count_break_sent(sent):
        nonlocal seen_sents
        if seen_sents >= sentences:
            return BREAK
        seen_sents += 1

    transform_sentences(inf, count_break_sent, outf)
    inf.close()
    outf.close()


@filter.command("sample")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def sample(inf, outf):
    """
    Sample the sentences in DEFAULT_SAMPLE_LINES (fixed) from inf
    """
    seen_sents = 0

    def count_break_sent(sent):
        nonlocal seen_sents
        if seen_sents >= DEFAULT_SAMPLE_MAX:
            return BREAK
        if seen_sents not in DEFAULT_SAMPLE_LINES:
            seen_sents += 1
            return BYPASS
        seen_sents += 1

    transform_sentences(inf, count_break_sent, outf)

    if seen_sents <= max(DEFAULT_SAMPLE_LINES):
        print("Not enough sentences in input to sample.")


class MultiFile:
    def __init__(self, *fps):
        self.fps = fps

    def write(self, payload):
        for fp in self.fps:
            fp.write(payload)

    def close(self, payload):
        for fp in self.fps:
            fp.close(payload)


def split_xml(inf, testf, trainf, sentences):
    from io import BytesIO

    been_inside = False
    seen_sents = 0
    head_bio = BytesIO()
    outf = MultiFile(testf, head_bio)
    stream = etree.iterparse(inf, events=("start", "end"))
    started = False
    find_instance = False
    switch_instance = None
    for event, elem in stream:
        if started:
            fixup_missing_text(event, elem, outf)
        if event == "start" and elem.tag == "sentence":
            if not been_inside:
                outf = testf
            been_inside = True
            seen_sents += 1
        if find_instance and event == "start" and elem.tag == "instance":
            switch_instance = elem.attrib["id"]
            find_instance = False
        write_event(event, elem, outf)
        if event == "end" and elem.tag == "sentence":
            if seen_sents == sentences:
                close_all(elem, outf)
                outf = trainf
                outf.write(head_bio.getvalue())
                find_instance = True
            free_elem(elem)
        started = True
    return switch_instance


@filter.command("split")
@click.argument("inf", type=click.File("rb"))
@click.argument("testf", type=click.File("wb"))
@click.argument("trainf", type=click.File("wb"))
@click.argument("keyin", type=click.File("r"), required=False)
@click.argument("testkey", type=click.File("w"), required=False)
@click.argument("trainkey", type=click.File("w"), required=False)
@click.option("--sentences", default=100)
def split(inf, testf, trainf, keyin, testkey, trainkey, sentences):
    """
    Put the first SENTENCES sentences from INF into TESTF and the rest into
    TRAINF.
    """
    switch_instance = split_xml(inf, testf, trainf, sentences)

    if keyin:
        switched = False
        for line in keyin:
            if line.split()[0] == switch_instance:
                switched = True
            if switched:
                trainkey.write(line)
            else:
                testkey.write(line)


@filter.command("join")
@click.argument("infs", nargs=-1, type=click.File("r"))
@click.argument("outf", nargs=1, type=click.File("w"))
def join(infs, outf):
    outf.write("<?xml version='1.0' encoding='UTF-8'?>\n")
    outf.write("<corpora>\n")
    for inf in infs:
        for line in inf:
            if line.startswith("<?xml"):
                continue
            outf.write(line)
    outf.write("</corpora>\n")


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


if __name__ == "__main__":
    filter()
