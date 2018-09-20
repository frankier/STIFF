import re
from .common import get_token_auto, get_substr_auto
from .mw_utils import multiword_variants
from .wordnet.cmn import Wordnet as WordnetCmn
from .gen import extract_auto, extract_tokenized
from stiff.tagging import Anchor

_cmn_trie = None


def get_cmn_token_auto():
    lang = WordnetCmn.lang()
    return get_token_auto(
        lang,
        (
            (l, wns, [var.split(" ") for var in multiword_variants(l)])
            for l, wns in WordnetCmn.lemma_names().items()
        ),
    )


def extract_zh_auto(line: str):
    return extract_auto(line, WordnetCmn, get_substr_auto(WordnetCmn), "zh-untok")


def extract_zh_tok(line: str):
    return extract_tokenized(line, WordnetCmn, get_cmn_token_auto(), "zh-tok")


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
