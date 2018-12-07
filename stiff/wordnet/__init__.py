from typing import List, Dict
from nltk.corpus import wordnet
from nltk.corpus.reader.wordnet import Lemma
from finntk.wordnet.reader import fiwn_encnt
from .base import ExtractableWordnet
from .utils import wn_lemma_map


def wn_lemma_keys(wn: str, lemma_name: str) -> List[Lemma]:
    if wn == "qf2":
        return fiwn_encnt.lemmas(lemma_name)
    else:
        return wordnet.lemmas(lemma_name, lang=wn)


def objify_lemmas(wn_to_lemma: Dict[str, List[str]]) -> Dict[str, List[Lemma]]:
    return {
        wn: [
            lemma_obj for lemma in lemma_list for lemma_obj in wn_lemma_keys(wn, lemma)
        ]
        for wn, lemma_list in wn_to_lemma.items()
    }


__all__ = ["ExtractableWordnet", "wn_lemma_keys", "wn_lemma_map", "objify_lemmas"]
