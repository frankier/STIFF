import ahocorasick
import pyahocorasick
from typing import Any, Dict, List, Tuple, Type, Iterator, Iterable

from stiff.wordnet import wn_lemma_map, ExtractableWordnet
from stiff.wordnet.utils import merge_lemma_maps
from .mw_utils import multiword_variants


def mk_substr_auto(wordnet: Type[ExtractableWordnet]) -> ahocorasick.Automaton:
    entries: List[Tuple[str, Dict[str, List[str]]]] = []
    for l, wns in wordnet.lemma_names().items():
        lfs = multiword_variants(l)
        for lf in lfs:
            entries.append((lf, wn_lemma_map(l, wns)))
    auto = ahocorasick.Automaton()
    for lf, lemma_map in dedup_entries(entries):
        auto.add_word(lf, (lf, lemma_map))
    auto.make_automaton()
    return auto


def dedup_entries(entries: List[Tuple[Any, Dict[str, List[str]]]]):
    entries.sort(key=lambda pair: pair[0])
    prev_key = None
    lemma_map_acc: Dict[str, List[str]] = {}
    for key, lemma_map in entries:
        if prev_key is not None and prev_key != key:
            yield prev_key, lemma_map_acc
            lemma_map_acc = {}
        lemma_map_acc = merge_lemma_maps(lemma_map_acc, lemma_map)
        prev_key = key
    yield prev_key, lemma_map_acc


def mk_token_auto(
    words: Iterator[Tuple[str, List[str], Iterable[Tuple[str, ...]]]]
) -> pyahocorasick.TokenAutomaton:
    entries: List[Tuple[Tuple[str, ...], Dict[str, List[str]]]] = []
    for l, wns, lf_token_list in words:
        for lf_tokens in lf_token_list:
            entries.append((tuple(lf_tokens), wn_lemma_map(l, wns)))
    # Deduplicate paths since we can have e.g. hyvää and hyvä both normalising to hyvä
    auto = pyahocorasick.TokenAutomaton()
    for lf_tokens, lemma_map in dedup_entries(entries):
        auto.add_word(lf_tokens, (lf_tokens, lemma_map))
    auto.make_automaton()
    return auto
