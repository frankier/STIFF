from nltk.corpus import wordnet
from plumbum.cmd import pipenv, npm
from plumbum import local
import pycountry
from json import loads
from itertools import product
from opus_api import opus_api
import click
from urllib.request import urlretrieve
from urllib.parse import urlparse, parse_qs
from os import makedirs
import zipfile
from os.path import join as pjoin


MAP_A3_LOCALE = {
    # Chinese is Mandarin by default
    'cmn': ['zh_zh', 'zh', 'zh_cn', 'zh_CN', 'zh_HK', 'zh_tw', 'zh_TW'],
}


_opus_langs = None


def get_opus_codes(la3):
    lang = pycountry.languages.get(alpha_3=la3)
    global _opus_langs
    if _opus_langs is None:
        _opus_langs = loads(opus_api.langs())
    extras = MAP_A3_LOCALE.get(lang.alpha_3, [])
    return set(
        ol['name']
        for ol in _opus_langs
        if (hasattr(lang, 'alpha_2')
            and (ol['name'] == lang.alpha_2
                 or ol['name'].startswith(lang.alpha_2 + '_')))
        or hasattr(lang, 'alpha_3') and ol['name'] == lang.alpha_3
        or ol['name'] in extras
    )


def get_name(url):
    parse = urlparse(url)
    assert parse.path == '/download.php'
    qs = parse_qs(parse.query)
    return qs['f'][0].split('.')[0]


@click.command('tag')
@click.argument('lang1')
@click.argument('lang2')
def fetch_bitexts(lang1, lang2):
    dir_name = "{}-{}".format(lang1, lang2)
    makedirs(dir_name, exist_ok=True)
    for l1o, l2o in product(get_opus_codes(lang1), get_opus_codes(lang2)):
        bitexts = loads(opus_api.get(l1o, l2o))
        for corpus in bitexts['corpora']:
            url = corpus['url']
            print("Downloading", url)
            fn, headers = urlretrieve(url)
            print("Downloaded -- unzipping")
            assert headers['Content-Type'] == 'application/zip'
            name = get_name(url)
            full_dir = pjoin(dir_name, name)
            makedirs(full_dir, exist_ok=True)
            zip = zipfile.ZipFile(fn, 'r')
            zip.extractall(full_dir)
            zip.close()


if __name__ == '__main__':
    fetch_bitexts()
