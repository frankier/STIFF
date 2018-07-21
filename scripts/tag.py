from nltk.corpus import wordnet
from nltk.corpus.reader.wordnet import WordNetError
import click
from itertools import chain

import stiff.fixes  # noqa
from finntk.wordnet.reader import fiwn_encnt, get_en_fi_maps
from finntk.wordnet.utils import en2fi_post

from stiff.writers import Writer
from stiff.extract import extract_full_zh, get_synset_set_fin
from stiff.corpus_read import read_opensubtitles2018
from stiff.utils import get_opencc

SYNS_TRACE = True
SIM_TRACE = False
COVERAGE_TRACE = True


def get_tok_idx(tok):
    for anchor in tok["anchors"]:
        if "token" in anchor:
            return anchor["token"]


def apply_lemmas(
    wn_lemmas,
    dest_tagging,
    source_tagging,
    base_support,
    align_map,
    preproc_rev_map=None,
):
    for dest_token, dest_tag in dest_tagging.iter_tags():
        wn, synset = dest_tag["synset"]
        if synset in wn_lemmas:
            # Trace back source synset
            support = base_support.copy()
            if preproc_rev_map:
                source_synset = preproc_rev_map[synset]
            else:
                source_synset = synset
            wn, source_token_idx = source_tagging.wnlemmas[source_synset]
            source_token = source_tagging.tokens[source_token_idx]
            # Get source
            source_tag_id = None
            for source_tag in source_token["tags"]:
                if source_tag["synset"][1] == source_synset:
                    source_tag_id = source_tag["id"]
                    break
            assert source_tag_id is not None
            support["transfer-from"] = source_tag_id
            # Check if it's aligned
            dest_token_idx = get_tok_idx(dest_token)
            aligned = (
                dest_token_idx is not None
                and source_token_idx is not None
                and align_map.get(dest_token_idx) == source_token_idx
            )
            if aligned:
                support["transfer-type"] = "aligned"
            else:
                support["transfer-type"] = "unaligned"
            aligned = False
            dest_tag.setdefault("supports", []).append(support)


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


def add_supports_onto(tagging1, tagging2, align_map):
    t1l = tagging1.lemma_set()
    t2l = tagging2.lemma_set()
    common_lemmas = t1l & t2l

    deriv, rev_map = expand_english_deriv(t2l)
    deriv_lemmas = t1l & deriv

    apply_lemmas(common_lemmas, tagging1, tagging2, {}, align_map)
    apply_lemmas(
        deriv_lemmas,
        tagging1,
        tagging2,
        {"transform-chain": ["deriv"]},
        align_map,
        rev_map,
    )


def add_supports(tagging1, tagging2, align):
    add_supports_onto(tagging1, tagging2, align.s2t)
    add_supports_onto(tagging2, tagging1, align.t2s)


def add_fi_ranks(fi_tagging):
    for token in fi_tagging.tokens:
        tag_counts = []
        for tag in token["tags"]:
            wn, synset_str = tag["synset"]
            lemma_str = tag["wnlemma"]
            if wn in ("fin", "qwf"):
                omw_synset = wordnet.synset(synset_str)
                fi2en, en2fi = get_en_fi_maps()
                fi_synset_key = en2fi_post(wordnet.ss2of(omw_synset))
                fi_synset = fiwn_encnt.of2ss(fi_synset_key)
            elif wn == "qf2":
                fi_synset = fiwn_encnt.synset(synset_str)
            else:
                assert False
            fi_lemma = None
            for lemma in fi_synset.lemmas():
                if lemma.name() == lemma_str:
                    fi_lemma = lemma
            if fi_lemma is None:
                tag_counts.append((0, tag))
            else:
                tag_counts.append((fiwn_encnt.lemma_count(fi_lemma), tag))
        tag_counts.sort(reverse=True, key=lambda x: x[0])
        prev_count = float("inf")
        rank = 1
        for count, tag in tag_counts:
            tag["rank"] = (rank, count)
            if count < prev_count:
                prev_count = count
                rank += 1


def write_anns(writer, lang, tagging):
    for tok in tagging.tokens:
        if isinstance(tok["token"], str):
            anchor = tok["token"]
        else:
            anchor = tok["token"]["surf"]
        for tag in tok["tags"]:
            writer.write_ann(lang, anchor, tok, tag)


def proc_line(writer, zh_untok, zh_tok, fi_tok, src, align):
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
    fi_tagging = get_synset_set_fin(fi_tok)
    zh_tagging = extract_full_zh(zh_untok, zh_tok)
    for id, (_token, tag) in enumerate(
        chain(fi_tagging.iter_tags(), zh_tagging.iter_tags())
    ):
        tag["id"] = id
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


@click.command("tag")
@click.argument("corpus")
@click.argument("output", type=click.File("w"))
@click.option("--cutoff", default=None, type=int)
def tag(corpus, output, cutoff):
    idx = 0
    imdb_id = None
    with Writer(output) as writer:
        for zh_untok, zh_tok, fi_tok, src, align in read_opensubtitles2018(corpus):
            srcs, next_imdb_id = src[:-1], src[-1]
            if next_imdb_id != imdb_id:
                if imdb_id is not None:
                    writer.end_subtitle()
                imdb_id = next_imdb_id
                writer.begin_subtitle(srcs, imdb_id)
            proc_line(writer, zh_untok, zh_tok, fi_tok, src, align)
            idx += 1
            if cutoff is not None and idx > cutoff:
                break
        writer.end_subtitle()


if __name__ == "__main__":
    tag()
