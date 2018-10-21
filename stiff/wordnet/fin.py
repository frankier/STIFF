from nltk.corpus import wordnet
from finntk.wordnet.reader import get_en_fi_maps, fiwn_encnt
from finntk.wordnet.utils import ss2pre
from .utils import merge_lemmas
from .base import ExtractableWordnet
from typing import Dict, List
from stiff.data.fixes import fix_all

fix_all()


def _map_qf2(lemma_obj):
    fi2en, en2fi = get_en_fi_maps()
    return fi2en[ss2pre(lemma_obj.synset())]


class Wordnet(ExtractableWordnet):
    _synset_mappers = {"qf2": _map_qf2}

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
