from .utils import merge_lemmas
from nltk.corpus import wordnet
from stiff.utils import get_opencc
from .utils import get_rev_map, synset_group_lemmas


def multi_lemma_names():
    return merge_lemmas(
        ("cmn", wordnet.all_lemma_names(lang="cmn")),
        ("qcn", (get_opencc().convert(l) for l in wordnet.all_lemma_names(lang="qcn"))),
        ("qwc", wordnet.all_lemma_names(lang="qwc")),
    )


def multi_lemma_keys(lemma):
    return synset_group_lemmas(
        {
            "cmn": wordnet.lemmas(lemma, lang="cmn"),
            "qcn": wordnet.lemmas(get_rev_map("qcn")(lemma), lang="qcn"),
            "qwc": wordnet.lemmas(lemma, lang="qwc"),
        }
    )
