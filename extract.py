import ahocorasick
import pygtrie
from nltk.corpus import wordnet
import opencc

from finntk import get_omorfi, get_token_positions, extract_lemmas_recurs

from abbrvs import has_abbrv

_substr_autos = {}
_fin_trie = None


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
            lemmas = extract_lemmas_recurs(subword)
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
        lemmas = extract_lemmas_recurs(token)
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
