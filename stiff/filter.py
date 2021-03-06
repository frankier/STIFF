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


class TournamentBase(ABC):
    @staticmethod
    @abstractmethod
    def key(ann):
        pass

    def proc_stream(self, inf, outf):
        return transform_sentences(inf, self.proc_sent, outf)

    @staticmethod
    def prepare_sent(sent):
        return ()

    def get_anns(self, sent, *extra):
        return sent.xpath("./annotations/annotation")

    @abstractmethod
    def proc_anns(self, anns):
        pass

    def proc_sent(self, sent):
        extra = self.prepare_sent(sent)
        anns = self.get_anns(sent, *extra)
        self.proc_anns(anns, *extra)


class NumRankTournamentBase(TournamentBase):
    @staticmethod
    @abstractmethod
    def rank(ann):
        pass

    def proc_anns(self, anns, *extra):
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


class RankTournament(NumRankTournamentBase):
    def __init__(self, do_dom=True, rm_ranks=()):
        self.do_dom = do_dom
        self.rm_ranks = rm_ranks
        super().__init__()


class DomOnlyRankTournament(NumRankTournamentBase):
    def __init__(self):
        self.do_dom = True
        self.rm_ranks = ()
        super().__init__()


class CmpTournament(TournamentBase):
    @staticmethod
    @abstractmethod
    def cmp(ann1, ann2):
        pass

    def proc_anns(self, anns, *extra):
        grouped = {}
        for ann in anns:
            key = self.key(ann)
            grouped.setdefault(key, []).append(ann)
        new_anns = []
        for key, group_anns in grouped.items():
            nondominated = set(range(len(group_anns)))
            for idx, ann in enumerate(group_anns):
                if idx not in nondominated:
                    continue
                for other_idx, other_ann in enumerate(group_anns[idx + 1 :], idx + 1):
                    if other_idx not in nondominated:
                        continue
                    cmp_res = self.cmp(ann, other_ann, *extra)
                    if cmp_res == -1:
                        nondominated.remove(idx)
                        break
                    elif cmp_res == 1:
                        nondominated.remove(other_idx)
                    else:
                        pass
            new_anns.extend((group_anns[idx] for idx in nondominated))
        trim_anns(anns, new_anns)


class SpanKeyMixin:
    @staticmethod
    def key(ann):
        return get_ann_pos(ann)


class HasSupportTournament(SpanKeyMixin, RankTournament):
    @staticmethod
    def rank(ann):
        return 1 if "support" in ann.attrib and ann.attrib["support"] else 0


class AlignTournament(SpanKeyMixin, RankTournament):
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


class SrcCharLenTournament(SpanKeyMixin, RankTournament):
    @staticmethod
    def rank(ann):
        if "support" not in ann.attrib:
            return 0
        max_len = 0
        for support_qs in ann.attrib["support"].split(" "):
            support = parse_qs_single(support_qs)
            cur_len = int(support["transfer-from-anchor-char-length"])
            if cur_len > max_len:
                max_len = cur_len
        return max_len


class SrcCharSpanTournament(SpanKeyMixin, CmpTournament):
    @staticmethod
    def cmp(ann1, ann2):
        """
        Returns  1 if ann1 dominates ann2
              | -1 if ann2 dominates ann1
              |  0 otherwise
        """

        def extract_spans(ann):
            for support_qs in ann.attrib["support"].split(" "):
                support_dict = parse_qs_single(support_qs)
                positions = parse_qs_single(
                    support_dict["transfer-from-anchor-positions"]
                )
                yield int(positions["char"]), int(
                    support_dict["transfer-from-anchor-char-length"]
                )

        def cmp_sup(sup1, sup2):
            """
            Returns  1 if sup1 spans sup2
                  | -1 if sup2 spans sup1
                  |  0 otherwise
            """
            char1, len1 = sup1
            char2, len2 = sup2
            end1 = char1 + len1
            end2 = char2 + len2
            if (char1 < char2 and end1 >= end2) or (char1 <= char2 and end1 > end2):
                return 1
            elif (char1 > char2 and end1 <= end2) or (char1 >= char2 and end1 < end2):
                return -1
            else:
                return 0

        if "support" not in ann1.attrib and "support" not in ann2.attrib:
            return 0

        ann1dom = any(
            (
                all((cmp_sup(span1, span2) == 1 for span2 in extract_spans(ann2)))
                for span1 in extract_spans(ann1)
            )
        )
        ann2dom = any(
            (
                all((cmp_sup(span2, span1) == 1 for span1 in extract_spans(ann1)))
                for span2 in extract_spans(ann2)
            )
        )
        if ann1dom and not ann2dom:
            return 1
        elif ann2dom and not ann1dom:
            return -1
        else:
            return 0


class FinnPOSMixin:
    @staticmethod
    def prepare_sent(sent):
        return (get_finnpos_analys(sent),)


class NaiveLemmaTournament(FinnPOSMixin, SpanKeyMixin, RankTournament):
    @staticmethod
    def rank(ann, finnpos_analys):
        if "wnlemma" not in ann.attrib or not ann.attrib["wnlemma"]:
            return 0
        tok, tok_len = get_ann_pos(ann)
        head_off = get_headword_offset(ann)
        finnpos_head, feats = finnpos_analys[tok + head_off]
        any_match = False
        for lemma_bit in ann.attrib["wnlemma"].split(" "):
            lemma_dict = parse_qs_single(lemma_bit)
            lemma = lemma_dict["l"]
            wn_head = lemma.split("_")[head_off]
            if finnpos_head == wn_head:
                any_match = True
        return 1 if any_match else 0


class NaivePosTournament(FinnPOSMixin, SpanKeyMixin, RankTournament):
    @staticmethod
    def rank(ann, finnpos_analys):
        tok, tok_len = get_ann_pos(ann)
        wn_pos = get_wn_pos(ann)
        head_off = get_headword_offset(ann)
        lemma, feats = finnpos_analys[tok + head_off]
        return lemmatized_pos_match(wn_pos, feats)


class LemmaPathTournament(SpanKeyMixin, RankTournament):
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


class NonDerivTournament(SpanKeyMixin, RankTournament):
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


class FreqRankDom(SpanKeyMixin, DomOnlyRankTournament):
    @staticmethod
    def rank(ann):
        return -int(ann.attrib["rank"])


class AlphabeticDom(SpanKeyMixin, DomOnlyRankTournament):
    @staticmethod
    def rank(ann):
        return ReverseOrder(ann.text)


def mk_conditional_tournament(ApplyTour, FilterTour, filter_vals):
    class ConditionalTournament(ApplyTour):
        @staticmethod
        def prepare_sent(sent):
            return ApplyTour.prepare_sent(sent), FilterTour.prepare_sent(sent)

        @staticmethod
        def key(ann):
            apply_key = ApplyTour.key(ann)
            filter_key = FilterTour.key(ann)
            assert apply_key == filter_key
            return apply_key

        def get_anns(self, sent, apply_extra, filter_extra):
            anns = super().get_anns(sent)
            return [
                ann
                for ann in anns
                if FilterTour.rank(ann, *filter_extra) in filter_vals
            ]

        @staticmethod
        def rank(ann, apply_extra, filter_extra):
            return ApplyTour.rank(ann, *apply_extra)

        @staticmethod
        def cmp(ann1, ann2, apply_extra, filter_extra):
            return ApplyTour.cmp(ann1, ann2, *apply_extra)

    return ConditionalTournament


SupportedOnlyFreqRank = mk_conditional_tournament(
    FreqRankDom, HasSupportTournament, filter_vals=(1,)
)


class PreferNonWikiTargetDom(SpanKeyMixin, RankTournament):
    @staticmethod
    def rank(ann):
        wordnets = set(ann.attrib["wordnets"].split(" "))
        return 1 if (wordnets - {"qwf"}) else 0


class PreferNonWikiSourceDom(SpanKeyMixin, RankTournament):
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


SupportedOnlyNonWikiSrc = mk_conditional_tournament(
    PreferNonWikiSourceDom, HasSupportTournament, filter_vals=(1,)
)


def greedy_max_span(positions):
    max_pos = 0
    for pos in positions:
        positions[pos].sort(reverse=True, key=lambda pair: pair[0])
        if pos > max_pos:
            max_pos = pos
    anns = []
    cur_pos = 0
    while cur_pos <= max_pos:
        while cur_pos not in positions:
            cur_pos += 1
            if cur_pos > max_pos:
                break
        if cur_pos > max_pos:
            break
        cur_len, ann = positions[cur_pos][0]
        anns.append(ann)
        for other_len, ann in positions[cur_pos][1:]:
            if other_len != cur_len:
                break
            anns.append(ann)
        cur_pos += cur_len
    return anns


class HypTournament(SpanKeyMixin, CmpTournament):
    @staticmethod
    def cmp(ann1, ann2):
        """
        Returns  1 if ann1 dominates ann2
              | -1 if ann2 dominates ann1
              |  0 otherwise
        """

        def hypernym_of(hyper, hypo):
            return len(hypo) > len(hyper) and hypo[: len(hyper)] == hyper

        def ann2ss(ann):
            from stiff.munge.utils import synset_id_of_ann
            from nltk.corpus import wordnet
            from finntk.wordnet.utils import pre_id_to_post

            synset_id = pre_id_to_post(synset_id_of_ann(ann))
            # TODO: proper handling of new FinnWordNet synsets
            if synset_id[0] == "9":
                return
            return wordnet.of2ss(synset_id)

        syn1 = ann2ss(ann1)
        syn2 = ann2ss(ann2)
        syn1_dom = False
        syn2_dom = False

        if syn1 is None or syn2 is None:
            return 0

        for hyp_path1 in syn1.hypernym_paths():
            for hyp_path2 in syn2.hypernym_paths():
                if hypernym_of(hyp_path1, hyp_path2):
                    syn1_dom = True
                elif hypernym_of(hyp_path2, hyp_path1):
                    syn2_dom = True

        if syn1_dom and not syn2_dom:
            return 1
        elif syn2_dom and not syn1_dom:
            return -1
        else:
            return 0


SupportedOnlyHypTournament = mk_conditional_tournament(
    HypTournament, HasSupportTournament, filter_vals=(1,)
)
