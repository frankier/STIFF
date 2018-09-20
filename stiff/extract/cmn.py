import re
from .common import mk_token_auto, mk_substr_auto
from .mw_utils import multiword_variants
from .gen import extract_auto, extract_tokenized
from stiff.tagging import Anchor, UntokenizedTagging, TokenizedTagging, Tagging
from stiff.wordnet.cmn import Wordnet as WordnetCmn
from pyahocorasick import TokenAutomaton


WHITESPACE_RE = re.compile(r"\s")


def mk_cmn_token_auto() -> TokenAutomaton:
    return mk_token_auto(
        (
            (l, wns, [var.split(" ") for var in multiword_variants(l)])
            for l, wns in WordnetCmn.lemma_names().items()
        )
    )


class CmnExtractor:
    def __init__(self) -> None:
        self.untok_auto = mk_substr_auto(WordnetCmn)
        self.tok_auto = mk_cmn_token_auto()

    def extract_untok(self, line: str) -> UntokenizedTagging:
        return extract_auto(line, WordnetCmn, self.untok_auto, "zh-untok")

    def extract_tok(self, line: str) -> TokenizedTagging:
        return extract_tokenized(line, WordnetCmn, self.tok_auto, "zh-tok")

    def extract(self, line_untok: str, line_tok: str) -> Tagging:
        untok_synsets = self.extract_untok(line_untok)
        tok_synsets = self.extract_tok(line_tok)

        def matcher(tok_tok: Anchor, untok_tok: Anchor) -> bool:
            # XXX: Aribitrary argument ordering required
            assert untok_tok.from_id == "zh-untok"
            assert tok_tok.from_id == "zh-tok"
            tok_char = tok_tok.char
            untok_char = untok_tok.char
            tok_adjust = line_tok.count(" ", 0, tok_char)
            untok_adjust = sum(
                1 for m in WHITESPACE_RE.finditer(line_untok, 0, untok_char)
            )
            return tok_char - tok_adjust == untok_adjust - untok_adjust

        return untok_synsets.combine_cross_toks(tok_synsets, matcher)
