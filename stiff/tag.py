from nltk.corpus import wordnet
from nltk.corpus.reader.wordnet import WordNetError
from itertools import chain
from copy import copy

import stiff.fixes  # noqa
from finntk.wordnet.reader import fiwn_encnt

from stiff.extract import extract_full_cmn, extract_full_fin
from stiff.corpus_read import WordAlignment
from stiff.utils import get_opencc
from stiff.tagging import Tagging, Token, TagSupport
from stiff.writers import Writer
from typing import Dict, Set, Optional


def get_tok_idx(tok: Token) -> Optional[int]:
    for anchor in tok.anchors:
        if anchor.token is not None:
            return anchor.token
    return None


def apply_lemmas(
    wn_lemmas: Set[str],
    dest_tagging: Tagging,
    source_tagging: Tagging,
    base_support: TagSupport,
    align_map: Dict[int, int],
    preproc_rev_map=None,
):
    for dest_token, dest_tag in dest_tagging.iter_tags():
        matching_synsets = set()
        for wn, synset in dest_tag.wn_synset_names:
            if synset in wn_lemmas:
                matching_synsets.add(synset)
        matching_synsets_list = list(matching_synsets)
        assert len(matching_synsets_list) <= 1
        if len(matching_synsets_list) == 1:
            synset = matching_synsets_list[0]
            # Trace back source synset
            support = copy(base_support)
            if preproc_rev_map:
                source_synset = preproc_rev_map[synset]
            else:
                source_synset = synset
            wn, source_token_idx = source_tagging.wnlemmas[source_synset]
            source_token = source_tagging.tokens[source_token_idx]
            # Get source
            source_tag_id = None
            for source_tag in source_token.tags:
                for synset_pair in source_tag.wn_synset_names:
                    if synset_pair[1] == source_synset:
                        source_tag_id = source_tag.id
                        break
            assert source_tag_id is not None
            support.transfer_from = source_tag_id
            # Check if it's aligned
            dest_token_idx = get_tok_idx(dest_token)
            aligned = (
                dest_token_idx is not None
                and source_token_idx is not None
                and align_map.get(dest_token_idx) == source_token_idx
            )
            if aligned:
                support.transfer_type = "aligned"
            else:
                support.transfer_type = "unaligned"
            aligned = False
            dest_tag.supports.append(support)


def no_expand(lemmas):
    return lemmas


def expand_english_deriv(lemmas):
    res = set()
    rev_map = {}
    for lemma_key in lemmas:
        try:
            synset = wordnet.synset(lemma_key)
        except WordNetError:
            # XXX: Should try and deal with FiWN lemma keys somehow
            continue
        for other_lemma in synset.lemmas():
            for deriv in other_lemma.derivationally_related_forms():
                deriv_synset = deriv.synset().name()
                res.add(deriv_synset)
                rev_map[deriv_synset] = lemma_key
    return res, rev_map


def add_supports_onto(tagging1, tagging2, align_map: Dict[int, int]):
    t1l = tagging1.lemma_set()
    t2l = tagging2.lemma_set()
    common_lemmas = t1l & t2l

    deriv, rev_map = expand_english_deriv(t2l)
    deriv_lemmas = t1l & deriv

    apply_lemmas(common_lemmas, tagging1, tagging2, TagSupport(), align_map)
    apply_lemmas(
        deriv_lemmas,
        tagging1,
        tagging2,
        TagSupport(transform_chain=["deriv"]),
        align_map,
        rev_map,
    )


def add_supports(tagging1: Tagging, tagging2: Tagging, align):
    add_supports_onto(tagging1, tagging2, align.s2t)
    add_supports_onto(tagging2, tagging1, align.t2s)


def add_fi_ranks(fi_tagging: Tagging):
    for token in fi_tagging.tokens:
        tag_counts = []
        for tag in token.tags:
            fi_lemma = None
            for wn, lemma_obj in tag.lemma_objs:
                if wn == "qf2":
                    fi_lemma = lemma_obj
            if fi_lemma is None:
                tag_counts.append((0, tag))
            else:
                tag_counts.append((fiwn_encnt.lemma_count(fi_lemma), tag))
        tag_counts.sort(reverse=True, key=lambda x: x[0])
        prev_count = float("inf")
        rank = 1
        for count, tag in tag_counts:
            tag.rank = (rank, count)
            if count < prev_count:
                prev_count = count
                rank += 1


def write_anns(writer: Writer, lang: str, tagging: Tagging):
    for tok in tagging.tokens:
        for tag in tok.tags:
            writer.write_ann(lang, tok, tag)


def proc_line(writer, zh_untok: str, zh_tok: str, fi_tok: str, align: WordAlignment):
    # XXX: It's pretty sloppy always converting chracter-by-character: will
    # definitely try to convert simple => simpler sometimes
    # print("#####")
    # print("")
    # print(zh_untok)
    # print(zh_tok)
    # print(fi_tok)
    opencc = get_opencc()
    zh_untok = opencc.convert(zh_untok)
    zh_tok = opencc.convert(zh_tok)
    fi_tagging = extract_full_fin(fi_tok)
    zh_tagging = extract_full_cmn(zh_untok, zh_tok)
    for id, (_token, tag) in enumerate(
        chain(fi_tagging.iter_tags(), zh_tagging.iter_tags())
    ):
        tag.id = id
    # if SYNS_TRACE:
    # print(fi_tok)
    # print(zh_untok)
    # print('s1tok, s1d', s1tok, s1d)
    # print('s2tok, s12', s2tok, s2d)
    # s1d_lemma_map = dict(s1d.keys())
    # s2d_lemma_map = dict(s2d.keys())
    # s1 = set(s1d_lemma_map.keys())
    # s2 = set(s2d_lemma_map.keys())

    add_supports(fi_tagging, zh_tagging, align)
    add_fi_ranks(fi_tagging)

    writer.begin_sent()
    writer.write_text("zh", zh_tok)
    writer.write_text("zh", zh_untok, is_tokenised=False)
    writer.write_text("fi", fi_tok)
    writer.start_anns()
    write_anns(writer, "fi", fi_tagging)
    write_anns(writer, "zh", zh_tagging)
    writer.end_anns()
    writer.end_sent()
