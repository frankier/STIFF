from itertools import chain
from copy import copy
from json import dumps

from finntk.wordnet.reader import fiwn_encnt

from stiff.data.fixes import fix_all
from stiff.extract import CmnExtractor, FinExtractor
from stiff.corpus_read import WordAlignment
from stiff.utils.opencc import get_opencc
from stiff.models import Anchor, Tagging, Token, TagSupport
from stiff.writers import Writer
from typing import Dict, List, Set, Optional, Tuple


fix_all()


def get_tok_idx(tok: Token) -> Optional[int]:
    for anchor in tok.anchors:
        if anchor.token is not None:
            return anchor.token
    return None


def iter_supports(source_tagging, source_canon_id):
    for source_token_idx in source_tagging.wnsynsets[source_canon_id]:
        source_token = source_tagging.tokens[source_token_idx]
        for source_tag in source_token.tags:
            if (
                source_tag.canonical_synset_id(source_tagging.wordnet)
                == source_canon_id
            ):
                yield source_token, source_tag


def anchor_positions(anchor: Anchor):
    if anchor.token is not None and anchor.token_length is not None:
        return range(anchor.token, anchor.token + anchor.token_length)
    elif anchor.token is not None:
        return [anchor.token]
    else:
        return []


def apply_lemmas(
    wn_canon_ids: Set[str],
    dest_tagging: Tagging,
    source_tagging: Tagging,
    base_support: TagSupport,
    align_map: Dict[int, List[int]],
    preproc_rev_map=None,
):
    for dest_token, dest_tag in dest_tagging.iter_tags():
        dest_canon_id = dest_tag.canonical_synset_id(dest_tagging.wordnet)
        if dest_canon_id not in wn_canon_ids:
            continue
        # Get aligned source positions
        source_poses = set()
        for dest_anchor in dest_token.anchors:
            for dest_pos in anchor_positions(dest_anchor):
                if dest_pos in align_map:
                    source_poses.update(align_map[dest_pos])
        # Trace back source synset
        if preproc_rev_map:
            source_canon_id = preproc_rev_map[dest_canon_id]
        else:
            source_canon_id = dest_canon_id
        # Add each support
        for source_token, source_tag in iter_supports(source_tagging, source_canon_id):
            support = copy(base_support)
            support.transfer_from = source_tag.id
            # Check if any are aligned
            aligned = any(
                (
                    source_pos in source_poses
                    for source_anchor in source_token.anchors
                    for source_pos in anchor_positions(source_anchor)
                )
            )
            if aligned:
                support.transfer_type = "aligned"
            else:
                support.transfer_type = "unaligned"
            dest_tag.supports.append(support)


def expand_english_deriv(tagging: Tagging) -> Tuple[Set[str], Dict[str, str]]:
    res = set()
    rev_map = {}
    for wn, lemma_obj in tagging.wn_synsets():
        for other_lemma in lemma_obj.synset().lemmas():
            for deriv in other_lemma.derivationally_related_forms():
                deriv_synset = tagging.wordnet.canonical_synset_id(wn, deriv)
                res.add(deriv_synset)
                rev_map[deriv_synset] = tagging.wordnet.canonical_synset_id(
                    wn, lemma_obj
                )
    return res, rev_map


def add_supports_onto(tagging1, tagging2, align_map: Dict[int, List[int]]):
    t1l = tagging1.canon_synset_id_set()
    t2l = tagging2.canon_synset_id_set()
    common_lemmas = t1l & t2l

    deriv, rev_map = expand_english_deriv(tagging2)
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


def proc_line(
    cmn_extractor: CmnExtractor,
    fin_extractor: FinExtractor,
    writer: Writer,
    zh_untok: str,
    zh_tok: str,
    fi_tok: str,
    align: WordAlignment,
):
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
    fi_tagging = fin_extractor.extract(fi_tok)
    zh_tagging = cmn_extractor.extract(zh_untok, zh_tok)
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
    fi_id = writer.write_text("fi", fi_tok)
    writer.write_gram(
        fi_id,
        "finnpos",
        dumps(
            [
                (fp_lemma, fp_feats)
                for _, fp_lemma, fp_feats in fin_extractor.finnpos_analys
            ]
        ),
    )
    writer.start_anns()
    write_anns(writer, "fi", fi_tagging)
    write_anns(writer, "zh", zh_tagging)
    writer.end_anns()
    writer.end_sent()
