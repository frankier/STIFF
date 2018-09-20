from nltk.corpus import wordnet
from stiff.data import get_data_path


def fix_cmn():
    wordnet.custom_lemmas(
        open(get_data_path("wn-data-cmn-fixed.tab")), lang="cmn"
    )


def add_omw_wikt():
    for lang, code in [("fin", "qwf"), ("cmn", "qwc")]:
        wordnet.custom_lemmas(
            open(get_data_path("wn-wikt-{}.tab".format(lang))), lang=code
        )


def fix_all():
    fix_cmn()
    add_omw_wikt()
