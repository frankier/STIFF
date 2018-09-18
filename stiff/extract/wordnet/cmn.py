from .utils import merge_lemmas
from nltk.corpus import wordnet
from stiff.utils import get_opencc
from .utils import get_rev_map
from .base import ExtractableWordnet
from typing import Dict, List, Tuple, Iterable
from nltk.corpus.reader import Lemma


class Wordnet(ExtractableWordnet):
    @staticmethod
    def lang() -> str:
        return "cmn"

    @staticmethod
    def lemma_names() -> Dict[str, List[str]]:
        return merge_lemmas(
            ("cmn", wordnet.all_lemma_names(lang="cmn")),
            (
                "qcn",
                (get_opencc().convert(l) for l in wordnet.all_lemma_names(lang="qcn")),
            ),
            ("qwc", wordnet.all_lemma_names(lang="qwc")),
        )

    @classmethod
    def lemma_keys(cls, lemma: str) -> Iterable[List[Tuple[str, Lemma]]]:
        return cls.synset_group_lemmas(
            {
                "cmn": wordnet.lemmas(lemma, lang="cmn"),
                "qcn": wordnet.lemmas(get_rev_map("qcn")(lemma), lang="qcn"),
                "qwc": wordnet.lemmas(lemma, lang="qwc"),
            }
        )
