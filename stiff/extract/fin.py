from .common import mk_token_auto
from .gen import extract_tokenized_iter
from finntk.wordnet import has_abbrv
from finntk.omor.extract import (
    extract_lemmas_span,
    extract_lemmas_recurs,
    extract_lemmas,
)
from finntk import get_omorfi, get_token_positions
from finntk.finnpos import sent_finnpos
from stiff.models import TokenizedTagging
from stiff.utils.automata import conf_net_search
from stiff.wordnet.fin import Wordnet as WordnetFin
import re
from typing import Dict, List, Set


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
        starts = get_token_positions(omor_toks, line)
        return self.extract_toks([tok["surf"] for tok in omor_toks], starts)

    def extract_toks(self, surfs: List[str], starts: List[int]):
        self.finnpos_analys = sent_finnpos(surfs)
        tagging = TokenizedTagging(WordnetFin)
        conf_net = []
        sources = []
        feats = []
        for token, (_fp_surf, fp_lemma, fp_feats) in zip(surfs, self.finnpos_analys):
            omor = extract_lemmas(token)
            recurs = extract_lemmas_recurs(token)
            tok_sources: Dict[str, List[str]] = {}
            tok_choices: Set[str] = set()

            def add(lemmas, source):
                for lemma in lemmas:
                    tok_sources.setdefault(lemma, []).append(source)
                tok_choices.update(lemmas)

            add((token,), "whole")
            add(omor, "omor")
            add(recurs, "recurs")
            add((fp_lemma,), "finnpos")
            sources.append(tok_sources)
            feats.append(fp_feats)
            conf_net.append(tok_choices)
        extract_tokenized_iter(
            tagging,
            conf_net_search(self.tok_auto, conf_net, lambda x: (x[0], x[1][0])),
            WordnetFin,
            surfs,
            starts,
            "fi-tok",
            sources,
            feats,
        )
        return tagging
