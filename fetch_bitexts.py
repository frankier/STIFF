from nltk.corpus import wordnet
from plumbum.cmd import pipenv, npm
from plumbum import local
import pycountry
from json import loads
from itertools import product
import click
import omorfi


MAP_A3_LOCALE = {
    # Chinese is Mandarin by default
    'cmn': ['zh_zh', 'zh', 'zh_cn', 'zh_CN'],
    # Hong Kong/Cantonese uses traditional characters same as Taiwanese (so I
    # suppose this is okay?)
    'qcn': ['zh_HK', 'zh_tw', 'zh_TW'],
}


def run_opus_api(*args):
    with local.cwd('opus'):
        new_path = "{}:{}".format(npm('bin').strip(), local.env['PATH'])
        with local.env(PATH=new_path):
            return pipenv('run', 'opus_api', *args)


_opus_langs = None


def get_opus_codes(lang):
    global _opus_langs
    if _opus_langs is None:
        _opus_langs = loads(run_opus_api('langs'))
    extras = MAP_A3_LOCALE.get(lang.alpha_3, [])
    return [
        ol['name']
        for ol in _opus_langs
        if (hasattr(lang, 'alpha_2')
            and (ol['name'] == lang.alpha_2
                 or ol['name'].startswith(lang.alpha_2 + '_')))
        or hasattr(lang, 'alpha_3') and ol['name'] == lang.alpha_3
        or ol['name'] in extras
    ]


def get_bitexts(l1, l2):
    for l1o, l2o in product(get_opus_codes(l1), get_opus_codes(l2)):
        print(run_opus_api('get', l1o, l2o))


def mk_tagged(l1, l2):
    get_bitexts(l1, l2)
    wordnet.lemmas(word, lang=lang)


def mk_tagged_all(main_lang_a3):
    main_lang = pycountry.languages.get(alpha_3=main_lang_a3)
    for second_lang_a3 in wordnet.langs():
        second_lang = pycountry.languages.get(alpha_3=second_lang_a3)
        mk_tagged(main_lang, second_lang)
        #lemmas = wordnet.lemmas(lemma, lang='fin')
        #wordnet


def mk_tagged_pair(l1a3, l2a3):
    l1 = pycountry.languages.get(alpha_3=l1a3)
    l2 = pycountry.languages.get(alpha_3=l2a3)
    mk_tagged(l1, l2)


@click.command('tag')
@click.argument('lang1')
@click.argument('lang2', required=False)
def tag(lang1, lang2=None):
    if lang2 is None:
        mk_tagged_all(lang1)
    else:
        mk_tagged_pair(lang1, lang2)


if __name__ == '__main__':
    tag()
