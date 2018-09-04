from dataclasses import dataclass, field, asdict
from nltk.corpus.reader import Lemma
from typing import Callable, Dict, Optional, List, Tuple, Iterator
from urllib.parse import urlencode


MaybeOmorToken = Dict[str, str]
LocToks = List[Tuple[int, int, str, List[str]]]


class DataUtilMixin:
    def urlencode(self):
        d = asdict(self)
        for k in list(d.keys()):
            if d[k] is None or d[k] == "":
                del d[k]
        return urlencode(d)


@dataclass
class Anchor(DataUtilMixin):
    from_id: str
    char: int
    token: Optional[int] = None
    token_length: Optional[int] = None


@dataclass
class TagSupport(DataUtilMixin):
    # XXX: Stringly typed
    transfer_type: str = ""
    transfer_from: Optional[int] = None
    transform_chain: List[str] = field(default_factory=list)


@dataclass
class TaggedLemma:
    lemma: str
    synset: List[Tuple[str, str]] = field(default_factory=list)
    wnlemma: List[str] = field(default_factory=list)
    lemma_obj: List[Lemma] = field(default_factory=list)
    id: Optional[int] = None
    supports: List[TagSupport] = field(default_factory=list)
    rank: Optional[Tuple[int, int]] = None

    def __eq__(self, other):
        return (
            self.lemma == other.lemma
            and self.synset == other.synset
            and self.wnlemma == other.wnlemma
            and self.lemma_obj == other.lemma_obj
        )


@dataclass
class Token:
    token: str
    anchors: List[Anchor]
    tags: List[TaggedLemma]


class Tagging:
    tokens: List[Token]
    wnlemmas: Dict[str, Tuple[str, int]]

    def __init__(self, tokens: Optional[List[Token]]=None) -> None:
        self.wnlemmas = {}
        if tokens is None:
            self.tokens = []
        else:
            self.tokens = tokens
            for tok_idx, tok in enumerate(self.tokens):
                self._index_tags(tok_idx, tok.tags)

    def _index_tags(self, tok_idx: int, tags: List[TaggedLemma]):
        for tag in tags:
            for synset in tag.synset:
                self._index_lemma(tok_idx, synset)

    def _index_lemma(self, tok_idx: int, synset: Tuple[str, str]):
        self.wnlemmas[synset[1]] = (synset[0], tok_idx)

    def lemma_set(self):
        return set(self.wnlemmas.keys())

    def add_tags(self, token: str, anchors: List[Anchor], tags: List[TaggedLemma]):
        self.tokens.append(Token(token, anchors, tags))
        self._index_tags(len(self.tokens) - 1, tags)

    def iter_tags(self) -> Iterator[Tuple[Token, TaggedLemma]]:
        for token in self.tokens:
            for tag in token.tags:
                yield token, tag

    def _combine(self, other: 'Tagging', matcher: Callable[[Token, Token], bool], combiner: Callable[[Token, Token], None]) -> 'Tagging':
        num_tokens = len(self.tokens)
        tok = self.tokens[:]
        for t2 in other.tokens:
            combined = False
            for idx in range(0, num_tokens):
                if matcher(tok[idx], t2):
                    combined = True
                    combiner(tok[idx], t2)
                    break
            if not combined:
                tok.append(t2)
        return Tagging(tok)

    def combine_cross_toks(self, other: 'Tagging', matcher: Callable[[Anchor, Anchor], bool]):
        def match(untok_tok: Token, tok_tok: Token) -> bool:
            # XXX: Aribitrary number of anchors required
            assert len(untok_tok.anchors) == 1
            assert len(tok_tok.anchors) == 1
            matched = untok_tok.token == tok_tok.token and matcher(
                untok_tok.anchors[0], tok_tok.anchors[0]
            )
            if matched:
                # XXX: Aribitrary ordering required
                assert untok_tok.tags == tok_tok.tags
                return True
            return False

        def combine(t1: Token, t2: Token):
            t1.token += t2.token

        return self._combine(other, match, combine)
