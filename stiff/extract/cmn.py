import re
import pygtrie
from .common import (
    multi_lemma_names,
    multiword_variants,
    wn_lemma_map,
    get_synset_set_auto,
    get_synset_set_tokenized,
)

_cmn_trie = None


def get_cmn_trie():
    global _cmn_trie
    if _cmn_trie is not None:
        return _cmn_trie
    _cmn_trie = pygtrie.Trie()
    for l, wns in multi_lemma_names("cmn").items():
        vars = multiword_variants(l)
        if len(vars) == 1:
            continue
        for var in vars:
            _cmn_trie[var.split(" ")] = wn_lemma_map(l, wns)
    return _cmn_trie


def extract_zh_auto(line):
    return get_synset_set_auto(line, "cmn", "zh-untok")


def extract_zh_tok(line):
    return get_synset_set_tokenized(line, "cmn", get_cmn_trie(), "zh-tok")


WHITESPACE_RE = re.compile(r"\s")


def extract_full_cmn(line_untok, line_tok):
    untok_synsets = extract_zh_auto(line_untok)
    tok_synsets = extract_zh_tok(line_tok)

    def matcher(untok_tok, tok_tok):
        # XXX: Aribitrary argument ordering required
        assert untok_tok["from"] == "zh-untok"
        assert tok_tok["from"] == "zh-tok"
        tok_char = tok_tok["char"]
        untok_char = untok_tok["char"]
        tok_adjust = line_tok.count(" ", 0, tok_char)
        untok_adjust = sum(1 for m in WHITESPACE_RE.finditer(line_untok, 0, untok_char))
        return tok_char - tok_adjust == untok_adjust - untok_adjust

    return untok_synsets.combine_cross_toks(tok_synsets, matcher)
