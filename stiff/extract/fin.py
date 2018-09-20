from .common import mk_token_auto
from .gen import extract_tokenized_iter
from finntk.wordnet import has_abbrv
from finntk.omor.extract import extract_lemmas_span
from finntk import get_omorfi, get_token_positions, extract_lemmas_recurs
from finntk.finnpos import sent_finnpos
from stiff.models import TokenizedTagging
from stiff.utils.automata import conf_net_search
from stiff.wordnet.fin import Wordnet as WordnetFin
import re


FIN_SPACE = re.compile(r" |_")


def _fin_token_conf_net(l):
    subwords = FIN_SPACE.split(l)
    old_paths = [()]
    paths = None
    for subword in subwords:
        paths = [
            path + (lemma,)
            for lemma in extract_lemmas_span(subword)
            for path in old_paths
        ]
        old_paths = paths
    return paths


def mk_fin_token_auto():
    return mk_token_auto(
        (
            (l, wns, _fin_token_conf_net(l))
            for l, wns in WordnetFin.lemma_names().items()
            if not has_abbrv(l)
        )
    )


class FinExtractor:
    def __init__(self) -> None:
        self.tok_auto = mk_fin_token_auto()

    def extract(self, line: str) -> TokenizedTagging:
        omorfi = get_omorfi()
        omor_toks = omorfi.tokenise(line)
        finnpos_analys = sent_finnpos([tok["surf"] for tok in omor_toks])
        starts = get_token_positions(omor_toks, line)
        tagging = TokenizedTagging(WordnetFin)
        conf_net = (
            extract_lemmas_recurs(token) | {fp_lemma}
            for token, (_fp_surf, fp_lemma, _fp_feats) in zip(omor_toks, finnpos_analys)
        )
        surfs = (tok["surf"] for tok in omor_toks)
        extract_tokenized_iter(
            tagging,
            conf_net_search(self.tok_auto, conf_net, lambda x: x[0]),
            WordnetFin,
            surfs,
            starts,
            "fi-tok",
        )

        return tagging
