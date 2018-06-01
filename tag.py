from nltk.corpus import wordnet
import click
import string
from itertools import chain

import fix_cmn  # noqa

from writers import Writer
from extract import extract_full_zh, get_synset_set_fin
from corpus_read import read_opensubtitles2018
from utils import get_opencc

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
        synset = dest_tag["wnlemma"][0]
        if synset in wn_lemmas:
            # Trace back source synset
            support = base_support.copy()
            if preproc_rev_map:
                source_synset = preproc_rev_map[synset]
            else:
                source_synset = synset
            source_token_idx = source_tagging.wnlemmas[source_synset]
            source_token = source_tagging.tokens[source_token_idx]
            # Get source
            source_tag_id = None
            for source_tag in source_token["tags"]:
                if source_tag["wnlemma"][0] == source_synset:
                    source_tag_id = source_tag["id"]
                    break
            assert source_tag_id is not None
            support["source"] = source_tag_id
            # Check if it's aligned
            dest_token_idx = get_tok_idx(dest_token)
            aligned = (
                dest_token_idx is not None
                and source_token_idx is not None
                and align_map.get(dest_token_idx) == source_token_idx
            )
            if aligned:
                support["type"] = "aligned-transfer"
            else:
                support["type"] = "transfer"
            aligned = False
            dest_tag.setdefault("support", []).append(support)


def unambg_tags(tags):
    return dict(
        ((i, wn_lemmas) for i, wn_lemmas in tags.items() if len(wn_lemmas) == 1)
    )


def count_chars(line):
    return sum((len(x.strip(string.punctuation)) for x in line.split()))


def get_covs(tags, toks, line):
    unambg = unambg_tags(tags)
    # tok cov
    num_toks = len(toks)
    if num_toks > 0:
        cov = len(tags.keys()) / num_toks
        unambg_cov = len(unambg) / num_toks
    else:
        cov = 0
        unambg_cov = 0
    # char cov
    chars_covered = [False] * len(line)
    chars_unambg_covered = [False] * len(line)
    for tok_idx, tag_idxes in tags.items():
        tok = toks[tok_idx]
        char_range = range(tok["start"], tok["start"] + len(tok["token"]))
        if len(tag_idxes) == 1:
            for char_idx in char_range:
                chars_unambg_covered[char_idx] = True
        for char_idx in char_range:
            chars_covered[char_idx] = True
    num_chars_covered = chars_covered.count(True)
    num_chars_unambg_covered = chars_unambg_covered.count(True)
    total_chars = count_chars(line)
    return (
        cov,
        unambg_cov,
        num_chars_covered / total_chars,
        num_chars_unambg_covered / total_chars,
    )


def cov_trace(df, tags, toks, line):
    # synsets in s1 covered by s2
    cov, unambg, char, char_unambg = get_covs(tags, toks, line)
    if COVERAGE_TRACE:
        print(
            f"cov: {cov} unambg: {unambg}\n" f"char: {char} char_unambg: {char_unambg}"
        )
    df.loc[len(df)] = [cov, unambg, char, char_unambg]


def no_expand(lemmas):
    return lemmas


def expand_english_deriv(lemmas):
    res = set()
    rev_map = {}
    for lemma_key in lemmas:
        synset = wordnet.synset(lemma_key)
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
        deriv_lemmas, tagging1, tagging2, {"preproc": ["deriv"]}, align_map, rev_map
    )


def add_supports(tagging1, tagging2, align):
    add_supports_onto(tagging1, tagging2, align.s2t)
    add_supports_onto(tagging2, tagging1, align.t2s)


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

    writer.begin_sent()
    writer.write_text("zh", zh_tok)
    writer.write_text("zh", zh_untok, is_tokenised=False)
    writer.write_text("fi", fi_tok)
    write_anns(writer, "fi", fi_tagging)
    write_anns(writer, "zh", zh_tagging)
    writer.end_sent()


@click.command("tag")
@click.argument("corpus")
@click.argument("output")
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
