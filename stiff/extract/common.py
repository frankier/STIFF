from collections import defaultdict
import ahocorasick
from typing import Dict, List, Tuple, DefaultDict, Type
from nltk.corpus.reader import Lemma
from pygtrie import Trie

from stiff.tagging import Tagging, Anchor, TaggedLemma, LocToks
from finntk.wordnet.utils import ss2pre
from .wordnet import wn_lemma_keys, wn_lemma_map, ExtractableWordnet
from .mw_utils import multiword_variants

_substr_autos: Dict[str, ahocorasick.Automaton] = {}


def get_substr_auto(wordnet: Type[ExtractableWordnet]) -> ahocorasick.Automaton:
    lang = wordnet.lang()
    if lang not in _substr_autos:
        auto = ahocorasick.Automaton()
        for l, wns in wordnet.lemma_names().items():
            lfs = multiword_variants(l)
            for lf in lfs:
                auto.add_word(lf, (lf, wn_lemma_map(l, wns)))
        auto.make_automaton()
        _substr_autos[lang] = auto
    return _substr_autos[lang]


def add_line_tags_single(tagging: Tagging, loc_toks: LocToks, from_id: str, wordnet: Type[ExtractableWordnet]):
    for token_idx, char, token, lemmas in loc_toks:
        tags = []
        for lemma in lemmas:
            for group in wordnet.lemma_keys(lemma):
                tag_group = TaggedLemma(token)
                tag_group.lemma_objs = group
                tags.append(tag_group)
        if tags:
            tagging.add_tags(
                token, [Anchor(from_id, char, token_idx)], tags
            )


def add_multi_tags(tagging: Tagging, from_id: str, path, wn_to_lemma: Dict[str, str], loc_toks_slice: LocToks):
    grouped_lemmas: DefaultDict[str, List[Tuple[str, Lemma]]] = defaultdict(list)
    for wn, lemma in wn_to_lemma.items():
        for lemma_obj in wn_lemma_keys(wn, lemma):
            grouped_lemmas[ss2pre(lemma_obj.synset())].append(
                (wn, lemma_obj)
            )
    tags = []
    for group in grouped_lemmas.values():
        tag_group = TaggedLemma(" ".join(path))
        tag_group.lemma_objs = group
        tags.append(tag_group)
    token_idx, char, _, _ = loc_toks_slice[0]
    tagging.add_tags(
        " ".join(
            [
                token
                for _, _, token, _ in loc_toks_slice[: len(path)]
            ]
        ),
        [
            Anchor(
                from_id,
                char,
                token_idx,
                len(path),
            )
        ],
        tags,
    )


def add_line_tags_multi(tagging: Tagging, trie: Trie, loc_toks: LocToks, from_id: str):
    for begin_token_idx, _, _, _ in loc_toks:
        cursors: List[Tuple[str, ...]] = [()]
        for cur_token_idx in range(begin_token_idx, len(loc_toks)):
            next_cursors: List[Tuple[str, ...]] = []
            (_, _, _, lemma_strs) = loc_toks[cur_token_idx]
            for cursor in cursors:
                for lemma_str in lemma_strs:
                    new_cursor: Tuple[str, ...] = cursor + (lemma_str,)
                    if trie.has_key(new_cursor):  # noqa: W601
                        add_multi_tags(
                            tagging,
                            from_id,
                            new_cursor,
                            trie[new_cursor],
                            loc_toks[begin_token_idx : cur_token_idx + 1],
                        )
                    if trie.has_subtrie(new_cursor):
                        next_cursors.append(new_cursor)
            if not len(next_cursors):
                break
            cursors = next_cursors
