import re
from pygtrie import Trie
from .common import get_substr_auto, wn_lemma_map
from .mw_utils import multiword_variants
from .wordnet.cmn import Wordnet as WordnetCmn
from .gen import extract_auto, extract_tokenized
from stiff.tagging import Anchor

_cmn_trie = None


def get_cmn_trie() -> Trie:
    global _cmn_trie
    if _cmn_trie is not None:
        return _cmn_trie
    _cmn_trie = Trie()
    for l, wns in WordnetCmn.lemma_names().items():
        vars = multiword_variants(l)
        if len(vars) == 1:
            continue
        for var in vars:
            _cmn_trie[var.split(" ")] = wn_lemma_map(l, wns)
    return _cmn_trie


def extract_zh_auto(line: str):
    return extract_auto(line, WordnetCmn, get_substr_auto(WordnetCmn), "zh-untok")


def extract_zh_tok(line: str):
    return extract_tokenized(line, WordnetCmn, get_cmn_trie(), "zh-tok")


WHITESPACE_RE = re.compile(r"\s")


def extract_full_cmn(line_untok: str, line_tok: str):
    untok_synsets = extract_zh_auto(line_untok)
    tok_synsets = extract_zh_tok(line_tok)

    def matcher(tok_tok: Anchor, untok_tok: Anchor) -> bool:
        # XXX: Aribitrary argument ordering required
        assert untok_tok.from_id == "zh-untok"
        assert tok_tok.from_id == "zh-tok"
        tok_char = tok_tok.char
        untok_char = untok_tok.char
        tok_adjust = line_tok.count(" ", 0, tok_char)
        untok_adjust = sum(1 for m in WHITESPACE_RE.finditer(line_untok, 0, untok_char))
        return tok_char - tok_adjust == untok_adjust - untok_adjust

    return untok_synsets.combine_cross_toks(tok_synsets, matcher)
