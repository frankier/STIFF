import ast
from abc import ABC, abstractmethod
from functools import reduce
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

    @abstractmethod
    def key(self, ann):
        pass

    @abstractmethod
    def rank(self, ann):
        pass

    def proc_stream(self, inf, outf):
        return transform_sentences(inf, self.proc_sent, outf)

    def prepare_sent(self, sent):
        return ()

    def proc_sent(self, sent):
        extra = self.prepare_sent(sent)
        anns = sent.xpath("./annotations/annotation")
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


class SpanKeyMixin:
    def key(self, ann):
        return get_ann_pos(ann)


class HasSupportTournament(SpanKeyMixin, Tournament):
    def rank(self, ann):
        return 1 if "support" in ann.attrib and ann.attrib["support"] else 0


class AlignTournament(SpanKeyMixin, Tournament):
    def rank(self, ann):
        if "support" not in ann.attrib:
            return 0
        have_aligned = False
        for support_qs in ann.attrib["support"].split(" "):
            support = parse_qs_single(support_qs)
            if support["transfer-type"] == "aligned":
                have_aligned = True
        return 1 if have_aligned else 0


class FinnPOSMixin:
    def prepare_sent(self, sent):
        return (get_finnpos_analys(sent),)


class NaiveLemmaTournament(FinnPOSMixin, SpanKeyMixin, Tournament):
    def rank(self, ann, finnpos_analys):
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
    def rank(self, ann, finnpos_analys):
        tok, tok_len = get_ann_pos(ann)
        wn_pos = get_wn_pos(ann)
        head_off = get_headword_offset(ann)
        lemma, feats = finnpos_analys[tok + head_off]
        return lemmatized_pos_match(wn_pos, feats)


class LemmaPathTournament(SpanKeyMixin, Tournament):
    def rank(self, ann):
        return (
            1
            if all(
                tok_path != "recur" for tok_path in ann.attrib["lemma-path"].split(" ")
            )
            else 0
        )


class NonDerivDom(SpanKeyMixin, Tournament):
    def rank(self, ann):
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
