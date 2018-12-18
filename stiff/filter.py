import ast
from abc import ABC, abstractmethod
from functools import reduce, total_ordering
import json

from stiff.utils import parse_qs_single
from stiff.utils.anns import get_ann_pos
from stiff.utils.xml import transform_sentences


def decode_dom_arg(proc):
    if proc == "dom":
        return True, ()
    elif proc == "rm":
        return False, (0,)


def get_wn_pos(ann):
    wn_ids = ann.text.split(" ")
    poses = [wn_id.rsplit(".", 2)[-2] for wn_id in wn_ids]
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


def get_finnpos_analys(sent):
    gram = sent.xpath("gram[@type='finnpos']")
    assert len(gram) == 1
    return json.loads(gram[0].text)


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


def trim_anns(anns, new_anns):
    for ann in anns:
        if ann not in new_anns:
            ann.getparent().remove(ann)


class Tournament(ABC):
    def __init__(self, do_dom=True, rm_ranks=()):
        self.do_dom = do_dom
        self.rm_ranks = rm_ranks

    @staticmethod
    @abstractmethod
    def key(ann):
        pass

    @staticmethod
    @abstractmethod
    def rank(ann):
        pass

    def proc_stream(self, inf, outf):
        return transform_sentences(inf, self.proc_sent, outf)

    @staticmethod
    def prepare_sent(sent):
        return ()

    def get_anns(self, sent, *extra):
        return sent.xpath("./annotations/annotation")

    def proc_sent(self, sent):
        extra = self.prepare_sent(sent)
        anns = self.get_anns(sent, *extra)
        new_anns = anns.copy()
        best_ranks = {}
        ranks = {}
        for ann in anns:
            key = self.key(ann)
            rank = self.rank(ann, *extra)
            ranks[ann] = rank
            if rank in self.rm_ranks:
                new_anns.remove(ann)
            elif self.do_dom:
                if key not in best_ranks or rank > best_ranks[key]:
                    best_ranks[key] = rank
        if self.do_dom:
            for ann in anns:
                key = self.key(ann)
                best_rank = best_ranks[key]
                if best_rank > ranks[ann]:
                    new_anns.remove(ann)
        trim_anns(anns, new_anns)


class DomOnlyTournament(Tournament):
    def __init__(self):
        return super().__init__()


class SpanKeyMixin:
    @staticmethod
    def key(ann):
        return get_ann_pos(ann)


class HasSupportTournament(SpanKeyMixin, Tournament):
    @staticmethod
    def rank(ann):
        return 1 if "support" in ann.attrib and ann.attrib["support"] else 0


class AlignTournament(SpanKeyMixin, Tournament):
    @staticmethod
    def rank(ann):
        if "support" not in ann.attrib:
            return 0
        have_aligned = False
        for support_qs in ann.attrib["support"].split(" "):
            support = parse_qs_single(support_qs)
            if support["transfer-type"] == "aligned":
                have_aligned = True
        return 1 if have_aligned else 0


class FinnPOSMixin:
    @staticmethod
    def prepare_sent(sent):
        return (get_finnpos_analys(sent),)


class NaiveLemmaTournament(FinnPOSMixin, SpanKeyMixin, Tournament):
    @staticmethod
    def rank(ann, finnpos_analys):
        tok, tok_len = get_ann_pos(ann)
        head_off = get_headword_offset(ann)
        finnpos_head, feats = finnpos_analys[tok + head_off]
        any_match = False
        for wnlemma_attr in ann.attrib["wnlemma"].split(" "):
            wn_head = wnlemma_attr.split("_")[head_off]
            if finnpos_head == wn_head:
                any_match = True
        return 1 if any_match else 0


class NaivePosTournament(FinnPOSMixin, SpanKeyMixin, Tournament):
    @staticmethod
    def rank(ann, finnpos_analys):
        tok, tok_len = get_ann_pos(ann)
        wn_pos = get_wn_pos(ann)
        head_off = get_headword_offset(ann)
        lemma, feats = finnpos_analys[tok + head_off]
        return lemmatized_pos_match(wn_pos, feats)


class LemmaPathTournament(SpanKeyMixin, Tournament):
    @staticmethod
    def rank(ann):
        return (
            1
            if all(
                tok_path != "recur" for tok_path in ann.attrib["lemma-path"].split(" ")
            )
            else 0
        )


@total_ordering
class ReverseOrder:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __eq__(self, other):
        return self.wrapped == other.wrapped

    def __lt__(self, other):
        return self.wrapped > other.wrapped


class NonDerivTournament(SpanKeyMixin, Tournament):
    @staticmethod
    def rank(ann):
        if "support" not in ann.attrib:
            return 0
        has_non_deriv = False
        for support_qs in ann.attrib["support"].split(" "):
            support = parse_qs_single(support_qs)
            if "transform-chain" not in support:
                return 0
            # XXX: Should be json
            transform_chain = ast.literal_eval(support["transform-chain"])
            if "deriv" not in transform_chain:
                has_non_deriv = True
        return 1 if has_non_deriv else 0


class FreqRankDom(SpanKeyMixin, DomOnlyTournament):
    @staticmethod
    def rank(ann):
        return -int(ann.attrib["rank"])


class AlphabeticDom(SpanKeyMixin, DomOnlyTournament):
    @staticmethod
    def rank(ann):
        return ReverseOrder(ann.text)


def mk_conditional_tournament(apply_tour, filter_tour, filter_vals):
    class ConditionalTournament(Tournament):
        @staticmethod
        def prepare_sent(sent):
            return apply_tour.prepare_sent(sent), filter_tour.prepare_sent(sent)

        @staticmethod
        def key(ann):
            apply_key = apply_tour.key(ann)
            filter_key = filter_tour.key(ann)
            assert apply_key == filter_key
            return apply_key

        def get_anns(self, sent, apply_extra, filter_extra):
            anns = super().get_anns(sent)
            return [
                ann
                for ann in anns
                if filter_tour.rank(ann, *filter_extra) in filter_vals
            ]

        @staticmethod
        def rank(ann, apply_extra, filter_extra):
            return apply_tour.rank(ann, *apply_extra)

    return ConditionalTournament


SupportedOnlyFreqRank = mk_conditional_tournament(
    FreqRankDom, HasSupportTournament, filter_vals=(1,)
)


class PreferNonWikiTargetDom(SpanKeyMixin, Tournament):
    @staticmethod
    def rank(ann):
        wordnets = set(ann.attrib["wordnets"].split(" "))
        return 1 if (wordnets - {"qwf"}) else 0


class PreferNonWikiSourceDom(SpanKeyMixin, Tournament):
    @staticmethod
    def rank(ann):
        if "support" not in ann.attrib:
            return 0
        transfer_from = set()
        for support_qs in ann.attrib["support"].split(" "):
            support = parse_qs_single(support_qs)
            transfer_from = support["transfer-from-wordnets"]
            transfer_from = set(transfer_from.split("+"))
        return 1 if (transfer_from - {"qwc"}) else 0
