from collections import defaultdict
import ahocorasick

from stiff.tagging import Tagging
from finntk.wordnet.utils import ss2pre
from .wordnet import multi_lemma_names, multi_lemma_keys, wn_lemma_keys, wn_lemma_map

_substr_autos = {}


def chr_to_maybe_space(chr, lfs):
    res = set()
    for lf in lfs:
        res.add(lf.replace(chr, ""))
        res.add(lf.replace(chr, " "))
    return res


def chrs_to_maybe_space(chrs, lf):
    res = [lf]
    for chr in chrs:
        res = chr_to_maybe_space(chr, res)
    return res


def multiword_variants(lf):
    return chrs_to_maybe_space(["_", "+", " "], lf)


def get_substr_auto(lang):
    if lang in _substr_autos:
        return _substr_autos[lang]
    _substr_autos[lang] = ahocorasick.Automaton()
    for l, wns in multi_lemma_names(lang).items():
        lfs = multiword_variants(l)
        for lf in lfs:
            _substr_autos[lang].add_word(lf, (lf, wn_lemma_map(l, wns)))
    _substr_autos[lang].make_automaton()
    return _substr_autos[lang]


def get_synset_set_auto(line, wn, id):
    auto = get_substr_auto(wn)
    tagging = Tagging()
    for tok_idx, (end_pos, (token, wn_to_lemma)) in enumerate(auto.iter(line)):
        grouped_lemmas = defaultdict(list)
        for wn, lemma in wn_to_lemma.items():
            for ((synset_name, lemma_name), lemma_obj) in wn_lemma_keys(wn, lemma):
                grouped_lemmas[ss2pre(lemma_obj.synset())].append(
                    (wn, synset_name, lemma_name, lemma_obj)
                )
        tags = []
        for group in grouped_lemmas.values():
            tag_group = {"lemma": token, "synset": [], "wnlemma": [], "lemma_obj": []}
            for wn, synset_name, lemma_name, lemma_obj in group:
                tag_group["synset"].append((wn, synset_name))
                tag_group["wnlemma"].append(lemma_name)
                tag_group["lemma_obj"].append(lemma_obj)
            tags.append(tag_group)
        tagging.add_tags(token, [{"from": id, "char": end_pos - len(token) + 1}], tags)
    return tagging


def add_line_tags_single(tagging, loc_toks, from_id, lang):
    for token_idx, char, token, lemmas in loc_toks:
        tags = []
        for lemma in lemmas:
            for group in multi_lemma_keys(lang, lemma):
                tag = {"lemma": lemma, "synset": [], "wnlemma": [], "lemma_obj": []}
                for ((synset_name, lemma_name), wni, lemma_obj) in group:
                    tag["synset"].append((wni, synset_name))
                    tag["wnlemma"].append(lemma_name)
                    tag["lemma_obj"].append(lemma_obj)
                tags.append(tag)
        if tags:
            tagging.add_tags(
                token, [{"from": from_id, "char": char, "token": token_idx}], tags
            )


def add_multi_tags(tagging, from_id, path, wn_to_lemma, loc_toks_slice):
    grouped_lemmas = defaultdict(list)
    for wn, lemma in wn_to_lemma.items():
        for ((synset_name, lemma_name), lemma_obj) in wn_lemma_keys(wn, lemma):
            grouped_lemmas[ss2pre(lemma_obj.synset())].append(
                (wn, synset_name, lemma_name, lemma_obj)
            )
    tags = []
    for group in grouped_lemmas.values():
        tag_group = {
            "lemma": " ".join(path),
            "synset": [],
            "wnlemma": [],
            "lemma_obj": [],
        }
        for wn, synset_name, lemma_name, lemma_obj in group:
            tag_group["synset"].append((wn, synset_name))
            tag_group["wnlemma"].append(lemma_name)
            tag_group["lemma_obj"].append(lemma_obj)
        tags.append(tag_group)
    token_idx, char, _, _ = loc_toks_slice[0]
    tagging.add_tags(
        " ".join(
            [
                token["surf"] if isinstance(token, dict) else token
                for _, _, token, _ in loc_toks_slice[: len(path)]
            ]
        ),
        [
            {
                "from": from_id,
                "char": char,
                "token": token_idx,
                "token_length": len(path),
            }
        ],
        tags,
    )


def add_line_tags_multi(tagging, trie, loc_toks, from_id, wn):
    for begin_token_idx, _, _, _ in loc_toks:
        cursors = [()]
        for cur_token_idx in range(begin_token_idx, len(loc_toks)):
            next_cursors = []
            (_, _, _, lemma_strs) = loc_toks[cur_token_idx]
            for cursor in cursors:
                for lemma_str in lemma_strs:
                    new_cursor = cursor + (lemma_str,)
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


def get_tokens_starts(tokens):
    start = 0
    for token in tokens:
        yield start
        start += len(token) + 1


def get_synset_set_tokenized(line, wn, trie, id):
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
    add_line_tags_multi(tagging, trie, loc_toks, id, wn)
    return tagging
