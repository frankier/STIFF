from os.path import dirname, join as pjoin
from nltk.corpus import wordnet

for lang, code in [("fin", "qwf"), ("cmn", "qwc")]:
    wordnet.custom_lemmas(
        open(pjoin(dirname(__file__), "wn-wikt-{}.tab".format(lang))), lang=code
    )
