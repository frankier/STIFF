from .utils import merge_lemmas
from nltk.corpus import wordnet
from stiff.utils.opencc import get_opencc
from .base import ExtractableWordnet
from typing import Dict, List
from stiff.data.fixes import fix_all

fix_all()


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
