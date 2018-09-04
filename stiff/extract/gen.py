from collections import defaultdict
from nltk.corpus.reader import Lemma
from stiff.tagging import Tagging, Anchor, TaggedLemma
from ahocorasick import Automaton
from .common import add_line_tags_single, add_line_tags_multi
from .wordnet import ExtractableWordnet, wn_lemma_keys
from typing import List, Tuple, DefaultDict, Type
from finntk.wordnet.utils import ss2pre
from pygtrie import Trie


def extract_auto(line: str, auto: Automaton, from_id: str):
    tagging = Tagging()
    for tok_idx, (end_pos, (token, wn_to_lemma)) in enumerate(auto.iter(line)):
        grouped_lemmas: DefaultDict[str, List[Tuple[str, Lemma]]] = defaultdict(list)
        for wn, lemma in wn_to_lemma.items():
            for lemma_obj in wn_lemma_keys(wn, lemma):
                grouped_lemmas[ss2pre(lemma_obj.synset())].append(
                    (wn, lemma_obj)
                )
        tags = []
        for group in grouped_lemmas.values():
            tag_group = TaggedLemma(token)
            tag_group.lemma_objs = group
            tags.append(tag_group)
        tagging.add_tags(token, [Anchor(from_id, end_pos - len(token) + 1)], tags)
    return tagging


def get_tokens_starts(tokens):
    start = 0
    for token in tokens:
        yield start
        start += len(token) + 1


def extract_tokenized(line: str, wn: Type[ExtractableWordnet], trie: Trie, id: str):
    tagging = Tagging()
    tokens = line.split(" ")
    loc_toks = list(
        zip(
            range(0, len(tokens)),
            get_tokens_starts(tokens),
            tokens,
            [[token] for token in tokens],
        )
    )
    add_line_tags_single(tagging, loc_toks, id, wn)
    add_line_tags_multi(tagging, trie, loc_toks, id)
    return tagging
