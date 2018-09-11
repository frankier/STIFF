from itertools import chain

from stiff.corpus_read import WordAlignment
from stiff.extract import extract_full_cmn, extract_full_fin
from stiff.tag import add_supports


def test_multiple_best_lemmas():
    zh_tok = "好莱坞"
    zh_untok = "好莱坞"
    fi_tok = "Hollywoodiin"
    align = WordAlignment("0-0")

    fi_tagging = extract_full_fin(fi_tok)
    zh_tagging = extract_full_cmn(zh_untok, zh_tok)
    for id, (_token, tag) in enumerate(
        chain(fi_tagging.iter_tags(), zh_tagging.iter_tags())
    ):
        tag.id = id

    add_supports(fi_tagging, zh_tagging, align)

    hollywoodiin = fi_tagging.tokens[0]

    supported = 0
    unsupported = 0
    for tag in hollywoodiin.tags:
        if len(tag.supports):
            supported += 1
            assert len(tag.supports) == 1
            assert tag.supports[0].transfer_type == 'aligned'
        else:
            unsupported += 1
    assert supported == 2
    assert unsupported == 1
