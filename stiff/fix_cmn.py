from os.path import dirname, join as pjoin
from nltk.corpus import wordnet

wordnet.custom_lemmas(
    open(pjoin(dirname(__file__), "..", "wn-data-cmn-fixed.tab")), lang="cmn"
)
