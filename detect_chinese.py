import click
import mafan
from mafan import text
import opencc
from collections import Counter


MAFAN_NAMES = {
    mafan.TRADITIONAL: 'traditional',
    mafan.SIMPLIFIED: 'simplified',
    mafan.EITHER: 'either',
    mafan.BOTH: 'both',
    mafan.NEITHER: 'neither',
}


def opencc_detect(text):
    s2t = opencc.convert(text, config='s2t.json')
    t2s = opencc.convert(text, config='t2s.json')
    if text == s2t and text == t2s:
        return 'either'
    elif text == s2t:
        return 'traditional'
    elif text == t2s:
        return 'simplified'
    else:
        return 'both/neither'


@click.command('detect-chinese')
@click.argument('corpus', type=click.File('r'))
def detect_chinese(corpus):
    count = Counter()
    for line in corpus:
        line = line.strip()
        print(line)
        mefan_id = text.identify(line)
        count[mefan_id] += 1
        print('Mefan says', MAFAN_NAMES[mefan_id])
        print('OpenCC says', opencc_detect(line))
    for id, cnt in count.items():
        print(MAFAN_NAMES[id], cnt)


if __name__ == '__main__':
    detect_chinese()
