from lxml import etree
import click
from stiff.utils import parse_qs_single
from stiff.utils.xml import (
    fixup_missing_text,
    transform_sentences,
    write_event,
    BYPASS,
    BREAK,
    free_elem,
    close_all,
    iter_sentences,
)
from stiff.data.constants import DEFAULT_SAMPLE_LINES, DEFAULT_SAMPLE_MAX
from stiff.filter import (
    decode_dom_arg,
    get_finnpos_analys,
    greedy_max_span,
    trim_anns,
    HasSupportTournament,
    AlignTournament,
    NaiveLemmaTournament,
    NaivePosTournament,
    LemmaPathTournament,
    NonDerivTournament,
    FreqRankDom,
    AlphabeticDom,
    SupportedOnlyFreqRank,
    PreferNonWikiTargetDom,
    PreferNonWikiSourceDom,
    SrcCharLenTournament,
    SrcCharSpanTournament,
)
from stiff.utils.anns import get_ann_pos, get_ann_pos_dict
from urllib.parse import urlencode
from more_itertools import peekable


@click.group()
def filter():
    """
    Filter the master STIFF corpus to produce less ambiguous or unambiguous
    versions.
    """
    pass


@filter.command("has-support-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--proc", type=click.Choice(["dom", "rm"]))
def filter_support(inf, outf, proc):
    """
    Remove annotations without any support at all.
    """

    return HasSupportTournament(*decode_dom_arg(proc)).proc_stream(inf, outf)


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
                supp = parse_qs_single(supp)
                trans_from = supp["transfer-from"]
                from_elem = elem.xpath(
                    "./annotations/annotation[@id='{}']".format(trans_from)
                )[0]
                from_wordnets = from_elem.attrib["wordnets"]
                anchor_positions = from_elem.attrib["anchor-positions"]
                for position in anchor_positions.split(" "):
                    from_anchor = parse_qs_single(position)
                    from_source = from_anchor["from-id"]
                from_lemma_path = from_elem.attrib["lemma-path"]
                from_anchor_char_length = len(from_elem.attrib["anchor"])
                del supp["transfer-from"]
                supp.update(
                    {
                        "transfer-from-wordnets": from_wordnets,
                        "transfer-from-source": from_source,
                        "transfer-from-lemma-path": from_lemma_path,
                        "transfer-from-anchor-positions": anchor_positions,
                        "transfer-from-anchor-char-length": from_anchor_char_length,
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


@filter.command("rm-ambg")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def rm_ambg(inf, outf):
    """
    Remove ambiguous annotations of the same span.
    """

    def sent_rm_ambg(sent):
        anns = sent.xpath("./annotations/annotation")
        new_anns = anns.copy()
        span_counts = {}
        for ann in anns:
            span = get_ann_pos(ann)
            if span not in span_counts:
                span_counts[span] = 0
            span_counts[span] += 1
        for ann in anns:
            span = get_ann_pos(ann)
            if span_counts[span] >= 2:
                new_anns.remove(ann)
        trim_anns(anns, new_anns)

    transform_sentences(inf, sent_rm_ambg, outf)


@filter.command("align-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--proc", type=click.Choice(["dom", "rm"]))
def filter_align_dom(inf, outf, proc):
    """
    Dominance filter:

    Remove annotations which are based on unaligned transfers when there is an
    annotation based on aligned transfers of the same token.
    """

    return AlignTournament(*decode_dom_arg(proc)).proc_stream(inf, outf)


@filter.command("non-deriv-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--proc", type=click.Choice(["dom", "rm"]))
def non_deriv_dom(inf, outf, proc):
    """
    Dominance filter:

    Remove annotations which are based on derived transfers when there is an
    annotation based on a non-derived transfer of the same token.
    """

    return NonDerivTournament(*decode_dom_arg(proc)).proc_stream(inf, outf)


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


@filter.command("unified-test-dev-split")
@click.argument("inf", type=click.File("rb"))
@click.argument("ingoldf", type=click.File("rb"))
@click.argument("keyin", type=click.File("rb"))
@click.argument("goldkeyin", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.argument("keyout", type=click.File("wb"))
def unified_test_dev_split(inf, ingoldf, keyin, goldkeyin, outf, keyout):
    gold_sent_iter = peekable(iter_sentences(ingoldf))
    rm_inst_ids = []

    def sent_rm_gold(sent):
        gold_sent = gold_sent_iter.peek(None)
        if gold_sent is not None and gold_sent.attrib["id"] == sent.attrib["id"]:
            for instance in sent.xpath("./instance"):
                rm_inst_ids.append(instance.attrib["id"])
            next(gold_sent_iter)
            return BYPASS

    transform_sentences(inf, sent_rm_gold, outf)

    def next_rm():
        try:
            return rm_inst_ids.pop(0)
        except IndexError:
            return None

    rm_id = next_rm()
    for line in keyin:
        if rm_id == line.split()[0]:
            rm_id = next_rm()
            continue
        keyout.write(line)


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
    content) keep only the one with the highest count, breaking ties with
    alphabetical-ness.

    TODO: Could use some other measure of frequency -- or lemma numbering/graph
    centrality measures
    """

    return FreqRankDom().proc_stream(inf, outf)


@filter.command("break-ties")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def break_ties(inf, outf):
    return AlphabeticDom().proc_stream(inf, outf)


@filter.command("supported-freq-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def supported_freq_dom(inf, outf):
    return SupportedOnlyFreqRank().proc_stream(inf, outf)


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
        starts = []
        for ann in anns:
            anchor_pos = get_ann_pos_dict(ann)
            anchor = ann.attrib["anchor"]
            starts.append(int(anchor_pos["char"]))
        starts.sort()
        char_positions = {}
        for ann in anns:
            anchor_pos = get_ann_pos_dict(ann)
            anchor = ann.attrib["anchor"]
            cur_start = int(anchor_pos["char"])
            cur_start_idx = starts.index(cur_start)
            anchor_len = len(anchor)
            span = 0
            while (
                cur_start_idx + span < len(starts)
                and starts[cur_start_idx + span] <= cur_start + anchor_len
            ):
                span += 1
            char_positions.setdefault(cur_start, []).append((span, ann))
        new_anns = greedy_max_span(char_positions)
        trim_anns(anns, new_anns)

    transform_sentences(inf, sent_span_dom, outf)


@filter.command("src-char-len-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def src_char_len_dom(inf, outf):
    """
    Dominance filter:

    Based on token character length in the source language.
    """

    return SrcCharLenTournament().proc_stream(inf, outf)


@filter.command("src-char-span-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def src_char_span_dom(inf, outf):
    """
    Dominance filter:

    Based on character spanning in the source language.
    """

    return SrcCharSpanTournament().proc_stream(inf, outf)


@filter.command("non-recurs-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--proc", type=click.Choice(["dom", "rm"]))
def finnpos_non_recurs_dom(inf, outf, proc):
    """
    Remove annotations with one part of their lemma supported by only a recurs.
    """

    return LemmaPathTournament(*decode_dom_arg(proc)).proc_stream(inf, outf)


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

    return NaiveLemmaTournament(*decode_dom_arg(proc)).proc_stream(inf, outf)


@filter.command("finnpos-naive-pos-dom")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--proc", type=click.Choice(["dom", "rm-dom", "rm", "rm-agg"]))
def finnpos_naive_pos_dom(inf, outf, proc):
    """
    FinnPOS Dominance filter: Use FinnPOS annotations to support certain
    annotations over others, in terms of POS or lemma.

    Naive POS filter: Based on matching exactly the POS. Either as requirement
    or dominance filter.
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

    return NaivePosTournament(do_dom, rm_ranks).proc_stream(inf, outf)


@filter.command("finnpos-rm-pos")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--level", type=click.Choice(["soft", "normal", "agg"]))
def finnpos_rm_pos(inf, outf, level):
    """
    Heuristic POS removal: Remove specific POSs altogether. Most commonly
    PRONOUN, since this POS never exists in WordNet.
    """

    def m(feat, val):
        def inner(feats):
            return feat in feats and feats[feat] == val

        return inner

    to_remove = [m("pos", "PRONOUN")]
    if level in ("normal", "agg"):
        to_remove.extend(
            (
                m("pos", "NUMERAL"),
                m("pos", "INTERJECTION"),
                m("pos", "CONJUNCTION"),
                m("pos", "PARTICLE"),
                m("pos", "PUNCTUATION"),
                m("proper", "PROPER"),
            )
        )
    if level == "agg":
        to_remove.append(m("pos", "ADPOSITION"))

    def sent_rm_pos(sent):
        finnpos_analys = get_finnpos_analys(sent)
        anns = sent.xpath("./annotations/annotation")
        new_anns = anns.copy()
        for ann in anns:
            tok, tok_len = get_ann_pos(ann)
            if tok_len != 1:
                continue
            props = finnpos_analys[tok][1]
            if any((match(props) for match in to_remove)):
                new_anns.remove(ann)
        trim_anns(anns, new_anns)

    transform_sentences(inf, sent_rm_pos, outf)


@filter.command("non-wiki-src")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--proc", type=click.Choice(["dom", "rm"]))
def non_wiki_src(inf, outf, proc):
    return PreferNonWikiSourceDom(*decode_dom_arg(proc)).proc_stream(inf, outf)


@filter.command("non-wiki-trg")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--proc", type=click.Choice(["dom", "rm"]))
def non_wiki_trg(inf, outf, proc):
    return PreferNonWikiTargetDom(*decode_dom_arg(proc)).proc_stream(inf, outf)


if __name__ == "__main__":
    filter()
