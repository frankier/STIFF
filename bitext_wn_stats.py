import itertools
from nltk.corpus import wordnet
import click
import re
import string
import pandas as pd

import fix_cmn # noqa
from finntk import get_omorfi, analysis_to_subword_dicts, get_token_positions, extract_lemmas_recurs

from writers import Writer
from extract import get_synset_set
from corpus_read import read_opensubtitles2018

SYNS_TRACE = True
SIM_TRACE = False
COVERAGE_TRACE = True


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
    num_toks = len(toks)
    if num_toks > 0:
        cov = len(tags.keys()) / num_toks
        unambg_cov = len(unambg) / num_toks
    else:
        cov = 0
        unambg_cov = 0
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


def write_anns(writer, lang, taggings, tokens, tokenised=True):
    for tok_idx, tags in taggings.items():
        tok = tokens[tok_idx]
        if isinstance(tok['token'], str):
            anchor = tok['token']
        else:
            anchor = tok['token']['surf']
        lemma = list(tok['lemmas'])[0]
        for tag in tags:
            writer.write_ann(lang, anchor, tok_idx, lemma, tag, is_tokenised=tokenised)


def proc_line(writer, zh_untok, zh_tok, fi_tok, src, align):
    s1tok, s1d = get_synset_set(fi_tok, 'fin')
    s2tok, s2d = get_synset_set(zh_untok, 'zh+')
    if SYNS_TRACE:
        print(fi_tok)
        print(zh_untok)
        print('s1tok, s1d', s1tok, s1d)
        print('s2tok, s12', s2tok, s2d)
    s1d_lemma_map = dict(s1d.keys())
    s2d_lemma_map = dict(s2d.keys())
    s1 = set(s1d_lemma_map.keys())
    s2 = set(s2d_lemma_map.keys())

    s1_tags, s2_tags = get_tags(
        s1, s1d_lemma_map, s1d,
        s2, s2d_lemma_map, s2d,
        expand_english_deriv, expand_english_deriv)

    writer.begin_sent()
    writer.write_text("zh", zh_tok)
    writer.write_text("zh", zh_untok, is_tokenised=False)
    writer.write_text("fi", fi_tok)
    write_anns(writer, "fi", s1_tags, s1tok)
    write_anns(writer, "zh", s2_tags, s2tok)
    writer.end_sent()


@click.command('tag')
@click.argument('corpus')
@click.argument('output')
@click.option('--cutoff', default=None, type=int)
def tag(corpus, output, cutoff):
    idx = 0
    imdb_id = None
    with Writer(output) as writer:
        for zh_untok, zh_tok, fi_tok, src, align in read_opensubtitles2018(corpus):
            srcs, next_imdb_id = src[:-1], src[-1]
            if next_imdb_id != imdb_id:
                if imdb_id is not None:
                    writer.end_subtitle()
                imdb_id = next_imdb_id
                writer.begin_subtitle(src, imdb_id)
            proc_line(writer, zh_untok, zh_tok, fi_tok, src, align)
            idx += 1
            if cutoff is not None and idx > cutoff:
                break
        writer.end_subtitle()


if __name__ == '__main__':
    tag()
