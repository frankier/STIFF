from nltk.corpus import wordnet

wordnet.custom_lemmas(open("wn-data-cmn-fixed.tab"), lang="cmn")
