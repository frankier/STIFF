from nltk.corpus import wordnet
from finntk.wordnet.reader import fiwn_encnt
from .utils import lemma_key, wn_lemma_map


def wn_lemma_keys(wn, lemma_name):
    if wn == "qf2":
        lemmas = fiwn_encnt.lemmas(lemma_name)
    else:
        lemmas = wordnet.lemmas(lemma_name, lang=wn)
    return [(lemma_key(lemma), lemma) for lemma in lemmas]


def multi_lemma_names(lang):
    if lang == "cmn":
        from .cmn import multi_lemma_names

        return multi_lemma_names()
    elif lang == "fin":
        from .fin import multi_lemma_names

        return multi_lemma_names()
    else:
        assert False


def multi_lemma_keys(lang, lemma):
    def wntag(wn, lemmas):
        return [[(wn, lemma)] for lemma in lemmas]

    if lang == "cmn":
        from .cmn import multi_lemma_keys

        lemmas = multi_lemma_keys(lemma)
    elif lang == "fin":
        from .fin import multi_lemma_keys

        lemmas = multi_lemma_keys(lemma)
    else:
        assert False
    return [
        [(lemma_key(lemma), wn, lemma) for (wn, lemma) in wnlemma] for wnlemma in lemmas
    ]


__all__ = ["multi_lemma_names", "multi_lemma_keys", "wn_lemma_keys", "wn_lemma_map"]
