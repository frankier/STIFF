from stiff.tagging import UntokenizedTagging, TokenizedTagging, Anchor, TaggedLemma
from ahocorasick import Automaton
from .wordnet import ExtractableWordnet, objify_lemmas
from typing import Dict, Type, Iterator, Tuple, List, Iterable


def extract_auto(
    line: str, wn: Type[ExtractableWordnet], auto: Automaton, from_id: str
) -> UntokenizedTagging:
    tagging = UntokenizedTagging(wn)
    for tok_idx, (end_pos, (token, wn_to_lemma)) in enumerate(auto.iter(line)):
        groups = wn.synset_group_lemmas(objify_lemmas(wn_to_lemma))
        tags = []
        for group in groups:
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


def extract_tokenized_iter(
    tagging: TokenizedTagging,
    iter: Iterator[Tuple[int, Tuple[List[str], Dict[str, str]]]],
    wordnet: Type[ExtractableWordnet],
    surfs: Iterable[str],
    starts: List[int],
    from_id: str,
):
    for end_pos, (lf_tokens, wn_to_lemma) in iter:
        start_pos = end_pos - len(lf_tokens) + 1
        groups = wordnet.synset_group_lemmas(objify_lemmas(wn_to_lemma))
        tags = []
        for group in groups:
            tag_group = TaggedLemma(" ".join(lf_tokens))
            tag_group.lemma_objs = group
            tags.append(tag_group)
        tagging.add_tags(
            " ".join(surfs),
            [Anchor(from_id, starts[start_pos], start_pos, len(lf_tokens))],
            tags,
        )


def extract_tokenized(
    line: str, wn: Type[ExtractableWordnet], auto: Automaton, id: str
) -> TokenizedTagging:
    tagging = TokenizedTagging(wn)
    tokens = line.split(" ")
    starts = list(get_tokens_starts(tokens))
    extract_tokenized_iter(tagging, auto.iter(tokens), wn, tokens, starts, id)
    return tagging
