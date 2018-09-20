import ahocorasick
import pyahocorasick
from typing import Dict, List, Tuple, Type, Iterator

from .wordnet import wn_lemma_map, ExtractableWordnet
from .mw_utils import multiword_variants

_substr_autos: Dict[str, ahocorasick.Automaton] = {}
_token_autos: Dict[str, pyahocorasick.TokenAutomaton] = {}


def get_substr_auto(wordnet: Type[ExtractableWordnet]) -> ahocorasick.Automaton:
    lang = wordnet.lang()
    if lang not in _substr_autos:
        auto = ahocorasick.Automaton()
        for l, wns in wordnet.lemma_names().items():
            lfs = multiword_variants(l)
            for lf in lfs:
                auto.add_word(lf, (lf, wn_lemma_map(l, wns)))
        auto.make_automaton()
        _substr_autos[lang] = auto
    return _substr_autos[lang]


def get_token_auto(lang: str, words: Iterator[Tuple[str, List[str], Tuple[str]]]) -> pyahocorasick.TokenAutomaton:
    if lang not in _token_autos:
        auto = pyahocorasick.TokenAutomaton()
        for l, wns, lf_token_list in words:
            for lf_tokens in lf_token_list:
                auto.add_word(lf_tokens, (lf_tokens, wn_lemma_map(l, wns)))
        auto.make_automaton()
        _token_autos[lang] = auto
    return _token_autos[lang]
