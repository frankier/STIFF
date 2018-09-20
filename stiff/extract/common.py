import ahocorasick
import pyahocorasick
from typing import List, Tuple, Type, Iterator, Iterable

from stiff.wordnet import wn_lemma_map, ExtractableWordnet
from .mw_utils import multiword_variants


def mk_substr_auto(wordnet: Type[ExtractableWordnet]) -> ahocorasick.Automaton:
    auto = ahocorasick.Automaton()
    for l, wns in wordnet.lemma_names().items():
        lfs = multiword_variants(l)
        for lf in lfs:
            auto.add_word(lf, (lf, wn_lemma_map(l, wns)))
    auto.make_automaton()
    return auto


def mk_token_auto(
    words: Iterator[Tuple[str, List[str], Iterable[Iterable[str]]]]
) -> pyahocorasick.TokenAutomaton:
    auto = pyahocorasick.TokenAutomaton()
    for l, wns, lf_token_list in words:
        for lf_tokens in lf_token_list:
            auto.add_word(lf_tokens, (lf_tokens, wn_lemma_map(l, wns)))
    auto.make_automaton()
    return auto
