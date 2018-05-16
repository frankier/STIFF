import itertools
from nltk.corpus import wordnet
import click
import ahocorasick
import pygtrie
import re
import opencc

from abbrvs import has_abbrv
import fix_cmn # noqa
from finntk import get_omorfi, analysis_to_dict

_substr_autos = {}
_fin_trie = None


def get_substr_auto(lang):
    if lang in _substr_autos:
        return _substr_autos[lang]
    _substr_autos[lang] = ahocorasick.Automaton()
    for l in wordnet.all_lemma_names(lang=lang):
        _substr_autos[lang].add_word(l, wordnet.lemmas(l, lang=lang))
    _substr_autos[lang].make_automaton()
    return _substr_autos[lang]


def get_synset_set_auto(line, lang):
    cmn_auto = get_substr_auto(lang)
    res = set()
    for (x, l) in cmn_auto.iter(line):
        for v in l:
            res.add(lemma_key(v))
    return res


EXTRA_WORD_ID = re.compile("_\d$")


def lemmatise(word_form):
    omorfi = get_omorfi()
    analyses = omorfi.analyse(word_form)
    res = set()
    for analysis in analyses:
        analysis_dict = analysis_to_dict(analysis['anal'])
        word_id = analysis_dict['word_id']
        extra_match = EXTRA_WORD_ID.match(word_id)
        if extra_match:
            word_id = word_id[:extra_match.start()]
        res.add(word_id.lower())
    return res


def get_fin_trie():
    global _fin_trie
    if _fin_trie is not None:
        return _fin_trie
    _fin_trie = pygtrie.Trie()
    for l in wordnet.all_lemma_names(lang='fin'):
        if '_' not in l or has_abbrv(l):
            continue
        paths = []
        for subword in l.split('_'):
            lemmas = lemmatise(subword)
            if paths:
                for lemma in lemmas:
                    for path in paths:
                        path.append(lemma)
            else:
                for lemma in lemmas:
                    paths.append([lemma])
        for path in paths:
            _fin_trie[path] = wordnet.lemmas(l, lang='fin')
    return _fin_trie


def lemma_key(lemma):
    return (lemma.synset().name(), lemma.name())


def get_synset_set_fin(line):
    trie = get_fin_trie()
    omorfi = get_omorfi()
    tokens = omorfi.tokenise(line)
    all_lemmas = []
    for token in tokens:
        lemmas = lemmatise(token)
        for lemma in lemmas:
            all_lemmas.append(lemma)
    res = set()
    for i, lemma in enumerate(all_lemmas):
        for wn_lemma in wordnet.lemmas(lemma, lang='fin'):
            print(wn_lemma, wn_lemma.derivationally_related_forms())
            res.add(lemma_key(wn_lemma))

        longest_prefix, multiword_lemmas = trie.longest_prefix(all_lemmas[i:])
        if multiword_lemmas is not None:
            for wn_lemma in multiword_lemmas:
                res.add(lemma_key(wn_lemma))
    return res


def get_synset_set_tokenized(line, lang):
    res = set()
    for word in line.split(' '):
        for lemma in wordnet.lemmas(word, lang=lang):
            res.add(lemma)
    return res


def get_synset_set_zh(line):
    return (get_synset_set_auto(line, 'cmn') |
            get_synset_set_auto(line, 'qcn'))


def get_synset_set_zh_pl_pl(line):
    return get_synset_set_zh_pl(line)


def get_synset_set_zh_pl(line):
    trad_line = opencc.convert(line, config='s2t.json')
    simp_line = opencc.convert(line, config='t2s.json')
    return (get_synset_set_zh(line) | 
            get_synset_set_zh(trad_line) | 
            get_synset_set_zh(simp_line))


def get_synset_set(line, lang):
    if lang == 'zh++':
        return get_synset_set_zh_pl_pl(line)
    elif lang == 'zh+':
        return get_synset_set_zh_pl(line)
    elif lang == 'zh':
        return get_synset_set_zh(line)
    elif lang in ('cmn', 'qcn'):
        return get_synset_set_auto(line, lang)
    elif lang == 'fin':
        return get_synset_set_fin(line)
    else:
        return get_synset_set_tokenized(line, lang)


@click.command('trace-wn')
@click.argument('lang1')
@click.argument('lang2')
@click.argument('corpus1', type=click.File('r'))
@click.argument('corpus2', type=click.File('r'))
@click.argument('alignment', type=click.File('r'), required=False)
def bitext_wn_stats(lang1, lang2, corpus1, corpus2,
                    alignment=None):
    if alignment is None:
        alignment = itertools.repeat(None)

    left_extra_count = 0
    right_extra_count = 0
    intersect_count = 0
    union_count = 0
    for line1, line2, align in zip(corpus1, corpus2, alignment):
        s1d = dict(get_synset_set(line1, lang1))
        s2d = dict(get_synset_set(line2, lang2))
        s1 = set(s1d.keys())
        s2 = set(s2d.keys())

        # s1 - s2
        s1_m_s2 = len(s1 - s2)
        left_extra_count += s1_m_s2

        # s2 - s1
        s2_m_s1 = len(s2 - s1)
        right_extra_count += s2_m_s1

        # s1 & s2
        s1_and_s2 = len(s1 & s2)
        intersect_count += s1_and_s2

        # s1 | s2
        s1_or_s2 = len(s1 | s2)
        union_count += s1_or_s2

        print(line1, line2)
        jaccard = s1_and_s2 / s1_or_s2 if s1_or_s2 > 0 else 0
        print(s1d)
        print(s2d)
        print(s1 & s2)
        print(f"s1 - s2: {s1_m_s2}; s2 - s1: {s2_m_s1}; s1 & s2: {s1_and_s2}; "
              f"s1 | s2 {s1_or_s2}; jaccard: {jaccard}")

        # synsets in s1 covered by s2
        # synsets in s2 covered by s1

    print(left_extra_count, right_extra_count, intersect_count, union_count)



if __name__ == '__main__':
    bitext_wn_stats()
