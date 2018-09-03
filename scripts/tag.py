from nltk.corpus import wordnet
from nltk.corpus.reader.wordnet import WordNetError
import click
from itertools import chain

import stiff.fixes  # noqa
from finntk.wordnet.reader import fiwn_encnt

from stiff.writers import Writer
from stiff.extract import extract_full_cmn, extract_full_fin, get_anchor
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
        matching_synsets = set()
        for wn, synset in dest_tag["synset"]:
            if synset in wn_lemmas:
                matching_synsets.add(synset)
        matching_synsets = list(matching_synsets)
        assert len(matching_synsets) <= 1
        if len(matching_synsets) == 1:
            synset = matching_synsets[0]
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
                for synset in source_tag["synset"]:
                    if synset[1] == source_synset:
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
            fi_lemma = None
            for lemma_obj, synset in zip(tag["lemma_obj"], tag["synset"]):
                wn, synset_str = synset
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
            tag["rank"] = (rank, count)
            if count < prev_count:
                prev_count = count
                rank += 1


def write_anns(writer, lang, tagging):
    for tok in tagging.tokens:
        anchor = get_anchor(tok)
        for tag in tok["tags"]:
            writer.write_ann(lang, anchor, tok, tag)


def proc_line(writer, zh_untok, zh_tok, fi_tok, align):
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
    """
    Tag Finnish and Chinese parts of OpenSubtitles2018 by writing all possible
    taggings for each token, and adding ways in which tagging from the two
    languages support each other. This can be made into an unambiguously tagged
    corpus filtering with the other scripts in this repository.
    """
    with Writer(output) as writer:
        for idx, zh_untok, zh_tok, fi_tok, srcs, imdb_id, new_imdb_id, align in read_opensubtitles2018(corpus):
            if new_imdb_id:
                if idx > 0:
                    writer.end_subtitle()
                writer.begin_subtitle(srcs, imdb_id)
            proc_line(writer, zh_untok, zh_tok, fi_tok, align)
            if cutoff is not None and idx > cutoff:
                break
        writer.end_subtitle()


if __name__ == "__main__":
    tag()
