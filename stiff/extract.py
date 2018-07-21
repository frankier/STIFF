import re
import ahocorasick
import pygtrie
from nltk.corpus import wordnet

from finntk import get_omorfi, get_token_positions, extract_lemmas_recurs
from finntk.omor.extract import extract_lemmas_span
from finntk.wordnet import has_abbrv
from finntk.wordnet.reader import fiwn_encnt
from finntk.finnpos import sent_finnpos

from stiff.utils import get_opencc

WORDNET_FILTERS = {"qcn": lambda x: get_opencc().convert(x)}

_substr_autos = {}
_rev_maps = {}
_fin_trie = None
_cmn_trie = None


FIN_SPACE = re.compile(r" |_")


def wn_lemma_map(l, wns):
    return {wn: get_rev_map(wn)(l) for wn in wns}


def merge_lemmas(*wn_lemmas_pairs):
    result = {}
    for (wn, lemmas) in wn_lemmas_pairs:
        for lemma in lemmas:
            result.setdefault(lemma, []).append(wn)
    return result


def multi_lemma_names(lang):
    if lang == "cmn":
        return merge_lemmas(
            ("cmn", wordnet.all_lemma_names(lang="cmn")),
            (
                "qcn",
                (get_opencc().convert(l) for l in wordnet.all_lemma_names(lang="qcn")),
            ),
            ("qwc", wordnet.all_lemma_names(lang="qwc")),
        )
    elif lang == "fin":
        return merge_lemmas(
            ("fin", wordnet.all_lemma_names(lang="fin")),
            ("qwf", wordnet.all_lemma_names(lang="qwf")),
            ("qf2", fiwn_encnt.all_lemma_names()),
        )
    else:
        assert False


def multi_lemma_keys(lang, lemma):
    def wntag(wn, lemmas):
        return [(wn, lemma) for lemma in lemmas]

    if lang == "cmn":
        lemmas = (
            wntag("cmn", wordnet.lemmas(lemma, lang="cmn"))
            + wntag("qcn", wordnet.lemmas(get_rev_map("qcn")(lemma), lang="qcn"))
            + wntag("qwc", wordnet.lemmas(lemma, lang="qwc"))
        )
    elif lang == "fin":
        lemmas = (
            wntag("fin", wordnet.lemmas(lemma, lang="fin"))
            + wntag("qf2", fiwn_encnt.lemmas(lemma))
            + wntag("qwf", wordnet.lemmas(lemma, lang="qwf"))
        )
    else:
        assert False
    return [(lemma_key(lemma), wn) for wn, lemma in lemmas]


def wn_lemma_keys(wn, lemma_name):
    if wn == "qf2":
        lemmas = fiwn_encnt.lemmas(lemma_name)
    else:
        lemmas = wordnet.lemmas(lemma_name, lang=wn)
    return [lemma_key(lemma) for lemma in lemmas]


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
                    self._index_lemma(tok_idx, tag["synset"])

    def _index_lemma(self, tok_idx, synset):
        self.wnlemmas[synset[1]] = (synset[0], tok_idx)

    def lemma_set(self):
        return set(self.wnlemmas.keys())

    def add_tags(self, token, anchors, tags):
        self.tokens.append({"token": token, "anchors": anchors, "tags": tags})
        for tag in tags:
            self._index_lemma(len(self.tokens) - 1, tag["synset"])

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
    auto = get_substr_auto(wn)
    tagging = Tagging()
    for tok_idx, (end_pos, (token, wn_to_lemma)) in enumerate(auto.iter(line)):
        tagging.add_tags(
            token,
            [{"from": id, "char": end_pos - len(token) + 1}],
            [
                {"lemma": token, "synset": (wn, synset_name), "wnlemma": lemma_name}
                for wn, lemma in wn_to_lemma.items()
                for (synset_name, lemma_name) in wn_lemma_keys(wn, lemma)
            ],
        )
    return tagging


def get_cmn_trie():
    global _cmn_trie
    if _cmn_trie is not None:
        return _cmn_trie
    _cmn_trie = pygtrie.Trie()
    for l, wns in multi_lemma_names("cmn").items():
        vars = multiword_variants(l)
        if len(vars) == 1:
            continue
        for var in vars:
            _cmn_trie[var.split(" ")] = wn_lemma_map(l, wns)
    return _cmn_trie


def get_fin_trie():
    global _fin_trie
    if _fin_trie is not None:
        return _fin_trie
    _fin_trie = pygtrie.Trie()
    for l, wns in multi_lemma_names("fin").items():
        if not FIN_SPACE.search(l) or has_abbrv(l):
            continue
        subwords = FIN_SPACE.split(l)
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
            _fin_trie[path] = wn_lemma_map(l, wns)
    return _fin_trie


TRIE_GETTERS = {"fin": get_fin_trie, "cmn": get_cmn_trie}


def lemma_key(lemma):
    return (lemma.synset().name(), lemma.name())


def add_line_tags_single(tagging, loc_toks, from_id, wn):
    for token_idx, char, token, lemmas in loc_toks:
        tags = []
        for lemma in lemmas:
            for ((synset_name, lemma_name), wni) in multi_lemma_keys(wn, lemma):
                tags.append(
                    {
                        "lemma": lemma,
                        "synset": (wni, synset_name),
                        "wnlemma": lemma_name,
                    }
                )
        if tags:
            tagging.add_tags(
                token, [{"from": from_id, "char": char, "token": token_idx}], tags
            )


def add_multi_tags(tagging, from_id, path, wn_to_lemma, loc_toks_slice):
    for wn, lemma in wn_to_lemma.items():
        tags = []
        for (synset_name, lemma_name) in wn_lemma_keys(wn, lemma):
            tags.append(
                {
                    "lemma": " ".join(path),
                    "synset": (wn, synset_name),
                    "wnlemma": lemma_name,
                }
            )
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


def get_synset_set_fin(line):
    trie = get_fin_trie()
    omorfi = get_omorfi()
    omor_toks = omorfi.tokenise(line)
    finnpos_analys = sent_finnpos([tok["surf"] for tok in omor_toks])
    starts = get_token_positions(omor_toks, line)
    tagging = Tagging()
    loc_toks = list(
        zip(
            range(0, len(omor_toks)),
            starts,
            omor_toks,
            (
                extract_lemmas_recurs(token) | {fp_lemma}
                for token, (_fp_surf, fp_lemma, _fp_feats) in zip(
                    omor_toks, finnpos_analys
                )
            ),
        )
    )
    add_line_tags_single(tagging, loc_toks, "fi-tok", "fin")
    add_line_tags_multi(tagging, trie, loc_toks, "fi-tok", "fin")

    return tagging


def get_tokens_starts(tokens):
    start = 0
    for token in tokens:
        yield start
        start += len(token) + 1


def get_synset_set_tokenized(line, wn, id):
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
    if wn in TRIE_GETTERS:
        trie = TRIE_GETTERS[wn]
        add_line_tags_multi(tagging, trie(), loc_toks, id, wn)
    return tagging


def extract_zh_auto(line):
    return get_synset_set_auto(line, "cmn", "zh-untok")


def extract_zh_tok(line):
    return get_synset_set_tokenized(line, "cmn", "zh-tok")


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
