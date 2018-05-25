import itertools
from nltk.corpus import wordnet
import click
import ahocorasick
import pygtrie
import re
import opencc
import string
import pandas as pd

from abbrvs import has_abbrv
import fix_cmn # noqa
from finntk import get_omorfi, analysis_to_dict, get_token_positions

from writers import UnifiedWriter, EuroSenseWriter

_substr_autos = {}
_fin_trie = None

SYNS_TRACE = True
SIM_TRACE = False
COVERAGE_TRACE = True


def get_substr_auto(lang):
    if lang in _substr_autos:
        return _substr_autos[lang]
    _substr_autos[lang] = ahocorasick.Automaton()
    for l in wordnet.all_lemma_names(lang=lang):
        _substr_autos[lang].add_word(l, (l, wordnet.lemmas(l, lang=lang)))
    _substr_autos[lang].make_automaton()
    return _substr_autos[lang]


def get_synset_set_auto(line, lang):
    cmn_auto = get_substr_auto(lang)
    tokens = []
    res = {}
    for tok_idx, (end_pos, (token, wn_lemmas)) in enumerate(cmn_auto.iter(line)):
        tokens.append({
            'token': token,
            'start': end_pos - len(token),
            'lemmas': [token],
        })
        for v in wn_lemmas:
            res.setdefault(lemma_key(v), []).append(tok_idx)
    return tokens, res


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
    omor_toks = omorfi.tokenise(line)
    starts = get_token_positions(omor_toks, line)
    tokens = []
    for token, start in zip(omor_toks, starts):
        lemmas = lemmatise(token)
        tokens.append({
            'token': token,
            'start': start,
            'lemmas': lemmas,
        })
    res = {}
    for tok_idx, token in enumerate(tokens):
        for lemma in token['lemmas']:
            for wn_lemma in wordnet.lemmas(lemma, lang='fin'):
                # XXX: Need to put this derivationally_related_forms expansion somewhere
                #print(wn_lemma, wn_lemma.derivationally_related_forms())
                #synset = wn_lemma.synset()
                #for other_lemma in synset.lemmas():
                #    print('other_lemma', other_lemma)
                #    for deriv in other_lemma.derivationally_related_forms():
                #        print('deriv', deriv)i
                res.setdefault(lemma_key(wn_lemma), []).append(tok_idx)

        # XXX: Have to deal with confusion net/lattice/trellis like structure
        #longest_prefix, multiword_lemmas = trie.longest_prefix(all_lemmas[i:])
        #if multiword_lemmas is not None:
            #for wn_lemma in multiword_lemmas:
                #res.add(lemma_key(wn_lemma))
    return tokens, res


def get_synset_set_tokenized(line, lang):
    tokens = []
    res = {}
    start = 0
    for tok_idx, token in enumerate(line.split(' ')):
        tokens.append({
            'token': token,
            'start': start,
            'lemmas': [token],
        })
        for v in wordnet.lemmas(token, lang=lang):
            res.setdefault(lemma_key(v), []).append(tok_idx)
        start += len(token) + 1
    return tokens, res


def combine_tok_synsets(toksyn1, toksyn2):
    (tok1, res1) = toksyn1
    (tok2, res2) = toksyn2
    tok = tok1.copy()
    tok2_to_tok = []
    for i2, t2 in enumerate(tok2):
        for i1, t1 in enumerate(tok1):
            if t2 == t1:
                tok2_to_tok.append(i1)
                break
        else:
            tok2_to_tok.append(len(tok))
            tok.append(t2)
    res = res1.copy()
    for l, tis in res2.items():
        if l not in res:
            res[l] = []
        for ti in tis:
            res[l].append(tok2_to_tok[ti])
    return tok, res


def get_synset_set_zh(line):
    return combine_tok_synsets(
        get_synset_set_auto(line, 'cmn'),
        get_synset_set_auto(line, 'qcn'))


def get_synset_set_zh_pl_pl(line):
    return get_synset_set_zh_pl(line)


def get_synset_set_zh_pl(line):
    trad_line = opencc.convert(line, config='s2t.json')
    simp_line = opencc.convert(line, config='t2s.json')
    return combine_tok_synsets(
        get_synset_set_zh(line),
        combine_tok_synsets(
            get_synset_set_zh(trad_line),
            get_synset_set_zh(simp_line)))


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


def apply_lemmas(wn_lemmas, lemma_map, lemma_tok_map):
    tags = {}
    for wn_lemma in wn_lemmas:
        s1_lemma = lemma_map[wn_lemma]
        tok_idxes = lemma_tok_map[(wn_lemma, s1_lemma)]
        for tok_idx in tok_idxes:
            tags.setdefault(tok_idx, set()).add(wn_lemma)
    return tags


def unambg_tags(tags):
    return dict((
        (i, wn_lemmas)
        for i, wn_lemmas in tags.items()
        if len(wn_lemmas) == 1))


def count_chars(line):
    return sum((len(x.strip(string.punctuation)) for x in line.split()))


def get_covs(tags, toks, line):
    unambg = unambg_tags(tags)
    # tok cov
    cov = len(tags.keys()) / len(toks)
    unambg_cov = len(unambg) / len(toks)
    # char cov
    chars_covered = [False] * len(line)
    chars_unambg_covered = [False] * len(line)
    for tok_idx, tag_idxes in tags.items():
        tok = toks[tok_idx]
        char_range = range(tok['start'], tok['start'] + len(tok['token']))
        if len(tag_idxes) == 1:
            for char_idx in char_range:
                chars_unambg_covered[char_idx] = True
        for char_idx in char_range:
            chars_covered[char_idx] = True
    num_chars_covered = chars_covered.count(True)
    num_chars_unambg_covered = chars_unambg_covered.count(True)
    total_chars = count_chars(line)
    return cov, unambg_cov, num_chars_covered / total_chars, num_chars_unambg_covered / total_chars


def cov_trace(df, tags, toks, line):
    # synsets in s1 covered by s2
    cov, unambg, char, char_unambg = get_covs(tags, toks, line)
    if COVERAGE_TRACE:
        print(f"cov: {cov} unambg: {unambg}\n"
              f"char: {char} char_unambg: {char_unambg}")
    df.loc[len(df)] = [cov, unambg, char, char_unambg]


def no_expand(lemmas):
    return lemmas


def expand_english_deriv(lemmas):
    res = lemmas.copy()
    for lemma_key in lemmas:
        synset = wordnet.synset(lemma_key)
        for other_lemma in synset.lemmas():
            for deriv in other_lemma.derivationally_related_forms():
                res.add(deriv.synset().name())
    print('expanded', res)
    return res


def get_tags(
        s1, s1d_lemma_map, s1d,
        s2, s2d_lemma_map, s2d,
        expand_s1=no_expand, expand_s2=no_expand):
    s1_expanded = expand_s1(s1)
    s2_expanded = expand_s2(s2)
    lemmas_s1 = s1 & s2_expanded
    lemmas_s2 = s1_expanded & s2

    s1_tags = apply_lemmas(lemmas_s1, s1d_lemma_map, s1d)
    s2_tags = apply_lemmas(lemmas_s2, s2d_lemma_map, s2d)
    print('s1_tags', s1_tags)
    print('s2_tags', s2_tags)
    return s1_tags, s2_tags


@click.command('trace-wn')
@click.argument('lang1')
@click.argument('lang2')
@click.argument('corpus1', type=click.File('r'))
@click.argument('corpus2', type=click.File('r'))
@click.option('--alignment', type=click.File('r'), default=None)
@click.option('--output', default=None)
@click.option('--format', default='eurosense')
@click.option('--cov-out', default='cov')
@click.option('--use-english-deriv/--no-use-english-deriv',
              default=False)
def bitext_wn_stats(lang1, lang2, corpus1, corpus2,
                    alignment, output, format,
                    cov_out, use_english_deriv):
    if alignment is None:
        alignment = itertools.repeat(None)

    if output:
        if format == 'eurosense':
            sense_writer = EuroSenseWriter(output)
        else:
            sense_writer = UnifiedWriter(output)

    df_cov1 = pd.DataFrame([], columns=['cov', 'unambg', 'char', 'unambg_char'])
    df_cov2 = pd.DataFrame([], columns=['cov', 'unambg', 'char', 'unambg_char'])
    left_extra_count = 0
    right_extra_count = 0
    intersect_count = 0
    union_count = 0
    for line1, line2, align in zip(corpus1, corpus2, alignment):
        s1tok, s1d = get_synset_set(line1, lang1)
        s2tok, s2d = get_synset_set(line2, lang2)
        if SYNS_TRACE:
            print(line1, line2)
            print('s1tok, s1d', s1tok, s1d)
            print('s2tok, s12', s2tok, s2d)
        s1d_lemma_map = dict(s1d.keys())
        s2d_lemma_map = dict(s2d.keys())
        s1 = set(s1d_lemma_map.keys())
        s2 = set(s2d_lemma_map.keys())

        if SIM_TRACE:
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

            jaccard = s1_and_s2 / s1_or_s2 if s1_or_s2 > 0 else 0
            print(s1d)
            print(s2d)
            print(s1 & s2)
            print(f"s1 - s2: {s1_m_s2}; s2 - s1: {s2_m_s1}; s1 & s2: {s1_and_s2}; "
                  f"s1 | s2 {s1_or_s2}; jaccard: {jaccard}")

        if use_english_deriv:
            s1_tags, s2_tags = get_tags(
                s1, s1d_lemma_map, s1d,
                s2, s2d_lemma_map, s2d,
                expand_english_deriv, expand_english_deriv)
        else:
            s1_tags, s2_tags = get_tags(
                s1, s1d_lemma_map, s1d,
                s2, s2d_lemma_map, s2d)

        cov_trace(df_cov1, s1_tags, s1tok, line1)
        cov_trace(df_cov2, s2_tags, s2tok, line2)

    df_cov1.to_csv(cov_out + '1.csv')
    df_cov2.to_csv(cov_out + '2.csv')

    if SIM_TRACE:
        print(left_extra_count, right_extra_count, intersect_count, union_count)

    return df_cov1, df_cov2


if __name__ == '__main__':
    bitext_wn_stats()
