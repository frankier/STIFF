from nltk.corpus import wordnet
from nltk.corpus.reader.wordnet import Lemma
from collections import defaultdict
from stiff.utils import get_opencc
from typing import Dict, Tuple, List, Iterator, Iterable, DefaultDict, Type
from stiff.extract.wordnet.base import ExtractableWordnet

WORDNET_FILTERS = {"qcn": lambda x: get_opencc().convert(x)}
_rev_maps: Dict[str, Dict[str, str]] = {}


def wn_lemma_map(l, wns):
    return {wn: get_rev_map(wn)(l) for wn in wns}


def merge_lemmas(*wn_lemmas_pairs: Tuple[str, Iterator[str]]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for (wn, lemmas) in wn_lemmas_pairs:
        for lemma in lemmas:
            result.setdefault(lemma, []).append(wn)
    return result


def synset_group_lemmas(
    wordnet_lemmas: Dict[str, List[Lemma]], wordnet: Type[ExtractableWordnet]
) -> Iterable[List[Tuple[str, Lemma]]]:
    grouped_lemmas: DefaultDict[str, List[Tuple[str, Lemma]]] = defaultdict(list)
    for wn, lemmas in wordnet_lemmas.items():
        for lemma_obj in lemmas:
            grouped_lemmas[wordnet.canonical_synset_id(wn, lemma_obj)].append(
                (wn, lemma_obj)
            )
    return grouped_lemmas.values()


def get_rev_map(lang):
    if lang not in WORDNET_FILTERS:
        return lambda x: x
    filter = WORDNET_FILTERS[lang]

    def rev_map(x):
        return _rev_maps[lang].get(x, x)

    if lang not in _rev_maps:
        m = {}
        for lemma in wordnet.all_lemma_names(lang=lang):
            filtered_lemma = filter(lemma)
            m[filtered_lemma] = lemma
        _rev_maps[lang] = m
    return rev_map
