from nltk.corpus import wordnet

for lang, code in [("fin", "qwf"), ("cmn", "qwc")]:
    wordnet.custom_lemmas(open("wn-wikt-{}.tab".format(lang)), lang=code)
