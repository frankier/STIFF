from dataclasses import dataclass, field, asdict
from nltk.corpus.reader import Lemma
from typing import (
    Callable, Dict, Optional, List, Tuple, Iterator, Set, Type, TYPE_CHECKING
)
from urllib.parse import urlencode

if TYPE_CHECKING:
    from stiff.extract.wordnet.base import ExtractableWordnet


MaybeOmorToken = Dict[str, str]
LocToks = List[Tuple[int, int, str, List[str]]]
CrossToksMatcher = Callable[["Anchor", "Anchor"], bool]
Matcher = Callable[["Token", "Token"], bool]
Combiner = Callable[["Token", "Token"], None]


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

    def urlencode(self):
        # Specialised for speed
        res = ["from_id=", self.from_id, "&char={}", str(self.char)]
        if self.token is not None:
            res.append("&token=")
            res.append(str(self.token))
        if self.token_length is not None:
            res.append("&token_length=")
            res.append(str(self.token_length))
        return "".join(res)


@dataclass
class TagSupport(DataUtilMixin):
    # XXX: Stringly typed
    transfer_type: str = ""
    transfer_from: Optional[int] = None
    transform_chain: List[str] = field(default_factory=list)


@dataclass
class TaggedLemma:
    lemma: str
    lemma_objs: List[Tuple[str, Lemma]] = field(default_factory=list)
    id: Optional[int] = None
    supports: List[TagSupport] = field(default_factory=list)
    rank: Optional[Tuple[int, int]] = None

    @property
    def wordnets(self) -> List[str]:
        return [wn for (wn, _lemma_obj) in self.lemma_objs]

    @property
    def lemma_names(self) -> Set[str]:
        return set((lemma_obj.name() for (_wn, lemma_obj) in self.lemma_objs))

    @property
    def synset_names(self) -> Set[str]:
        return set((lemma_obj.synset().name() for (_wn, lemma_obj) in self.lemma_objs))

    @property
    def wn_synset_names(self) -> List[Tuple[str, str]]:
        return [(wn, lemma_obj.synset().name()) for (wn, lemma_obj) in self.lemma_objs]

    def canonical_synset_id(self, wordnet: Type['ExtractableWordnet']):
        cur_id = None
        for wn, lemma_obj in self.lemma_objs:
            new_id = wordnet.canonical_synset_id(wn, lemma_obj)
            if cur_id is not None:
                assert cur_id == new_id
            cur_id = new_id
        return cur_id

    def __eq__(self, other: object):
        if not isinstance(other, TaggedLemma):
            return False
        return self.lemma == other.lemma and self.lemma_objs == other.lemma_objs


@dataclass
class Token:
    token: str
    anchors: List[Anchor]
    tags: List[TaggedLemma]


class Tagging:
    tokens: List[Token]
    wnsynsets: Dict[str, int]
    wordnet: Type['ExtractableWordnet']

    def __init__(
        self, wordnet: Type['ExtractableWordnet'], tokens: Optional[List[Token]] = None
    ) -> None:
        self.wordnet = wordnet
        self.wnsynsets = {}
        if tokens is None:
            self.tokens = []
        else:
            self.tokens = tokens
            for tok_idx, tok in enumerate(self.tokens):
                self._index_tags(tok_idx, tok.tags)

    def _index_tags(self, tok_idx: int, tags: List[TaggedLemma]):
        for tag in tags:
            self.wnsynsets[tag.canonical_synset_id(self.wordnet)] = tok_idx

    def canon_synset_id_set(self):
        return set(self.wnsynsets.keys())

    def wn_synsets(self):
        for tok_idx, tok in enumerate(self.tokens):
            for tag in tok.tags:
                for wn, lemma_obj in tag.lemma_objs:
                    yield wn, lemma_obj

    def add_tags(self, token: str, anchors: List[Anchor], tags: List[TaggedLemma]):
        tok = Token(token, anchors, tags)
        tok_idx = len(self.tokens)
        self.tokens.append(tok)
        self._index_tags(tok_idx, tags)

    def iter_tags(self) -> Iterator[Tuple[Token, TaggedLemma]]:
        for token in self.tokens:
            for tag in token.tags:
                yield token, tag

    def _combine(
        self, other: "Tagging", matcher: Matcher, combiner: Combiner
    ) -> "Tagging":
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
        return Tagging(self.wordnet, tok)


class UntokenizedTagging(Tagging):
    def combine_cross_toks(
        self, other_tok: "TokenizedTagging", matcher: CrossToksMatcher
    ) -> Tagging:
        return other_tok.combine_cross_toks(self, matcher)


class TokenizedTagging(Tagging):
    def combine_cross_toks(
        self, other_untok: "UntokenizedTagging", matcher: CrossToksMatcher
    ) -> Tagging:
        def match(tok_tok: Token, untok_tok: Token) -> bool:
            # XXX: Aribitrary number of anchors required
            assert len(untok_tok.anchors) == 1
            assert len(tok_tok.anchors) == 1
            matched = untok_tok.token == tok_tok.token and matcher(
                tok_tok.anchors[0], untok_tok.anchors[0]
            )
            if matched:
                # XXX: Aribitrary ordering required
                assert untok_tok.tags == tok_tok.tags
                return True
            return False

        def combine(tok_tok: Token, untok_tok: Token):
            tok_tok.anchors += untok_tok.anchors

        return self._combine(other_untok, match, combine)
