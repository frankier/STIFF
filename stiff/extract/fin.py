import pygtrie
from .common import (
    multi_lemma_names,
    wn_lemma_map,
    add_line_tags_single,
    add_line_tags_multi,
)
from finntk.wordnet import has_abbrv
from finntk.omor.extract import extract_lemmas_span
from finntk import get_omorfi, get_token_positions, extract_lemmas_recurs
from finntk.finnpos import sent_finnpos
from stiff.tagging import Tagging
import re


FIN_SPACE = re.compile(r" |_")
_fin_trie = None


def get_fin_trie():
    global _fin_trie
    if _fin_trie is not None:
        return _fin_trie
    _fin_trie = pygtrie.Trie()
    for l, wns in multi_lemma_names("fin").items():
        if not FIN_SPACE.search(l) or has_abbrv(l):
            continue
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
        for path in paths:
            _fin_trie[path] = wn_lemma_map(l, wns)
    return _fin_trie


def extract_full_fin(line: str):
    trie = get_fin_trie()
    omorfi = get_omorfi()
    omor_toks = omorfi.tokenise(line)
    finnpos_analys = sent_finnpos([tok["surf"] for tok in omor_toks])
    starts = get_token_positions(omor_toks, line)
    tagging = Tagging()
    loc_toks = list(
        zip(
            range(0, len(omor_toks)),
            starts,
            (tok["surf"] for tok in omor_toks),
            (
                extract_lemmas_recurs(token) | {fp_lemma}
                for token, (_fp_surf, fp_lemma, _fp_feats) in zip(
                    omor_toks, finnpos_analys
                )
            ),
        )
    )
    add_line_tags_single(tagging, loc_toks, "fi-tok", "fin")
    add_line_tags_multi(tagging, trie, loc_toks, "fi-tok", "fin")

    return tagging
