import re
import ahocorasick
import pygtrie
from nltk.corpus import wordnet

from finntk import get_omorfi, get_token_positions, extract_lemmas_recurs
from finntk.omor.extract import extract_lemmas_span
from finntk.wordnet import has_abbrv
from finntk.finnpos import sent_finnpos

from stiff.utils import get_opencc

WORDNET_FILTERS = {"qcn": lambda x: get_opencc().convert(x)}

_substr_autos = {}
_rev_maps = {}
_fin_trie = None


def same_tags(tags1, tags2):
    def filter_tags(tags):
        return [{k: v for k, v in t.items() if k != "id"} for t in tags]

    return filter_tags(tags1) == filter_tags(tags2)


class Tagging:
    def __init__(self, tokens=None):
        self.wnlemmas = {}
        if tokens is None:
            self.tokens = []
        else:
            self.tokens = tokens
            for tok_idx, tok in enumerate(self.tokens):
                for tag in tok["tags"]:
                    self._index_lemma(tok_idx, tag["wnlemma"])

    def _index_lemma(self, tok_idx, lemma):
        self.wnlemmas[lemma[0]] = tok_idx

    def lemma_set(self):
        return set(synset for synset in self.wnlemmas)

    def add_tags(self, token, anchors, tags):
        self.tokens.append({"token": token, "anchors": anchors, "tags": tags})
        for tag in tags:
            self._index_lemma(len(self.tokens) - 1, tag["wnlemma"])

    def iter_tags(self):
        for token in self.tokens:
            for tag in token["tags"]:
                yield token, tag

    def _combine(self, other, matcher, combiner):
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

    def combine_cross_wn(self, other):
        def match(t1, t2):
            assert len(t1["anchors"]) == 1
            assert len(t2["anchors"]) == 1
            return t1["token"] == t2["token"] and t1["anchors"][0] == t2["anchors"][0]

        def combine(t1, t2):
            if len(t1["tags"]) == 0 and len(t2["tags"]) == 0:
                return
            # XXX: Aribitrary limitation: Currently all lemmas must be the same
            lemma = t1["tags"][0]["lemma"] if t1["tags"] else t2["tags"][0]["lemma"]
            for other_tag in t2["tags"]:
                assert other_tag["lemma"] == lemma
                combined = False
                for tag in t1["tags"][:]:
                    assert tag["lemma"] == lemma
                    if other_tag["wnlemma"] == tag["wnlemma"]:
                        tag["wordnet"] |= other_tag["wordnet"]
                        combined = True
                if not combined:
                    t1["tags"].append(other_tag)

        return self._combine(other, match, combine)

    def combine_cross_toks(self, other, matcher):
        def match(untok_tok, tok_tok):
            # XXX: Aribitrary number of anchors required
            assert len(untok_tok["anchors"]) == 1
            assert len(tok_tok["anchors"]) == 1
            matched = untok_tok["token"] == tok_tok["token"] and matcher(
                untok_tok["anchors"][0], tok_tok["anchors"][0]
            )
            if matched:
                # XXX: Aribitrary ordering required
                assert same_tags(untok_tok["tags"], tok_tok["tags"])
                return True
            return False

        def combine(t1, t2):
            t1["token"] += t2["token"]

        return self._combine(other, match, combine)


def get_substr_auto(lang):
    if lang in _substr_autos:
        return _substr_autos[lang]
    _substr_autos[lang] = ahocorasick.Automaton()
    filter = WORDNET_FILTERS.get(lang)
    for l in wordnet.all_lemma_names(lang=lang):
        if filter is not None:
            lf = filter(l)
        else:
            lf = l
        _substr_autos[lang].add_word(lf, (lf, wordnet.lemmas(l, lang=lang)))
    _substr_autos[lang].make_automaton()
    return _substr_autos[lang]


def get_rev_map(lang):
    if lang not in WORDNET_FILTERS:
        return lambda x: x
    filter = WORDNET_FILTERS[lang]

    def rev_map(x):
        return _rev_maps[lang].get(x, x)

    if lang not in _rev_maps:
        m = {}
        for lemma in wordnet.all_lemma_names(lang=lang):
            filtered_lemma = filter(lemma)
            m[filtered_lemma] = lemma
        _rev_maps[lang] = m
    return rev_map


def get_synset_set_auto(line, wn, id):
    cmn_auto = get_substr_auto(wn)
    tagging = Tagging()
    for tok_idx, (end_pos, (token, wn_lemmas)) in enumerate(cmn_auto.iter(line)):
        tagging.add_tags(
            token,
            [{"from": id, "char": end_pos - len(token) + 1}],
            [
                {"lemma": token, "wordnet": {wn}, "wnlemma": lemma_key(v)}
                for v in wn_lemmas
            ],
        )
    return tagging


def get_fin_trie():
    global _fin_trie
    if _fin_trie is not None:
        return _fin_trie
    _fin_trie = pygtrie.Trie()
    for l in wordnet.all_lemma_names(lang="fin"):
        if "_" not in l or has_abbrv(l):
            continue
        subwords = l.split("_")
        old_paths = [()]
        paths = None
        for subword in subwords:
            paths = [
                path + (lemma,)
                for lemma in extract_lemmas_span(subword)
                for path in old_paths
            ]
            old_paths = paths
        for path in paths:
            _fin_trie[path] = wordnet.lemmas(l, lang="fin")
    return _fin_trie


def lemma_key(lemma):
    return (lemma.synset().name(), lemma.name())


def get_synset_set_fin(line):
    trie = get_fin_trie()
    omorfi = get_omorfi()
    omor_toks = omorfi.tokenise(line)
    finnpos_analys = sent_finnpos([tok["surf"] for tok in omor_toks])
    starts = get_token_positions(omor_toks, line)
    tagging = Tagging()
    loc_toks = list(zip(range(0, len(omor_toks)), starts, omor_toks, finnpos_analys))
    for token_idx, char, token, (_fp_surf, fp_lemma, _fp_feats) in loc_toks:
        lemmas = extract_lemmas_recurs(token) | {fp_lemma}
        tags = []
        for lemma in lemmas:
            for wn_lemma in wordnet.lemmas(lemma, lang="fin"):
                tags.append(
                    {"lemma": lemma, "wordnet": {"fin"}, "wnlemma": lemma_key(wn_lemma)}
                )
        tagging.add_tags(
            token, [{"from": "fi-tok", "char": char, "token": token_idx}], tags
        )

    for token_idx, char, token, (_fp_surf, fp_lemma, _fp_feats) in loc_toks:
        loc_toks[token_idx] = (
            token_idx,
            char,
            token,
            extract_lemmas_span(token) | {fp_lemma},
        )

    def intersect_trie_line(loc_toks_slice):
        def traverse_cb(path_conv, path, children, lemmas=None):
            def recurse():
                if len(path) < len(loc_toks_slice):
                    # Recurse by iterating over children
                    return list(children)

            if len(path) == 0:
                recurse()
                return
            matches = False
            if len(path) > len(loc_toks_slice):
                return
            (_, _, _, lemma_strs) = loc_toks_slice[len(path) - 1]
            for lemma_str in lemma_strs:
                if lemma_str == path[-1]:
                    matches = True
            if not matches:
                return
            if lemmas is not None:
                tags = []
                for wn_lemma in lemmas:
                    tags.append(
                        {
                            "lemma": " ".join(path),
                            "wordnet": {"fin"},
                            "wnlemma": lemma_key(wn_lemma),
                        }
                    )
                token_idx, char, _, _ = loc_toks_slice[0]
                tagging.add_tags(
                    " ".join(
                        [
                            token["surf"]
                            for _, _, token, _ in loc_toks_slice[: len(path)]
                        ]
                    ),
                    [
                        {
                            "from": "fi-tok",
                            "char": char,
                            "token": token_idx,
                            "token_length": len(path),
                        }
                    ],
                    tags,
                )
            # Recurse by iterating over children
            recurse()

        return traverse_cb

    for token_idx, _, _, _ in loc_toks:
        trie.traverse(intersect_trie_line(loc_toks[token_idx:]))

    return tagging


def get_synset_set_tokenized(line, wn, id):
    tagging = Tagging()
    start = 0
    for tok_idx, token in enumerate(line.split(" ")):
        tagging.add_tags(
            token,
            [{"from": id, "char": start, "token": tok_idx}],
            [
                {"lemma": token, "wordnet": {wn}, "wnlemma": lemma_key(v)}
                for v in wordnet.lemmas(get_rev_map(wn)(token), lang=wn)
            ],
        )
        start += len(token) + 1
    return tagging


def extract_zh_auto(line):
    return get_synset_set_auto(line, "cmn", "zh-untok").combine_cross_wn(
        get_synset_set_auto(line, "qcn", "zh-untok")
    )


def extract_zh_tok(line):
    return get_synset_set_tokenized(line, "cmn", "zh-tok").combine_cross_wn(
        get_synset_set_tokenized(line, "qcn", "zh-tok")
    )


WHITESPACE_RE = re.compile(r"\s")


def extract_full_zh(line_untok, line_tok):
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
