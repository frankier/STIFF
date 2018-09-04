from nltk.corpus import wordnet
from finntk.wordnet.reader import get_en_fi_maps, fiwn_encnt
from finntk.wordnet.utils import ss2pre
from .utils import merge_lemmas, synset_group_lemmas
from .base import ExtractableWordnet
from typing import Dict, List, Tuple
from nltk.corpus.reader import Lemma


class Wordnet(ExtractableWordnet):
    @staticmethod
    def lang() -> str:
        return "fin"

    @staticmethod
    def lemma_names() -> Dict[str, List[str]]:
        return merge_lemmas(
            ("fin", wordnet.all_lemma_names(lang="fin")),
            ("qwf", wordnet.all_lemma_names(lang="qwf")),
            ("qf2", fiwn_encnt.all_lemma_names()),
        )

    @staticmethod
    def lemma_keys(lemma: str) -> List[List[Tuple[str, Lemma]]]:
        fi2en, en2fi = get_en_fi_maps()
        return synset_group_lemmas(
            {
                "fin": wordnet.lemmas(lemma, lang="fin"),
                "qf2": fiwn_encnt.lemmas(lemma),
                "qwf": wordnet.lemmas(lemma, lang="qwf"),
            },
            {"qf2": lambda lemma_obj: fi2en[ss2pre(lemma_obj.synset())]},
        )
