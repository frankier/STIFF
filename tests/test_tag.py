from itertools import chain

from stiff.corpus_read import WordAlignment
from stiff.extract import get_extractor
from stiff.tag import add_supports


def tag(fi_tok, zh_tok, zh_untok, align):
    fi_tagging = get_extractor("FinExtractor").extract(fi_tok)
    zh_tagging = get_extractor("CmnExtractor").extract(zh_untok, zh_tok)
    for id, (_token, tag) in enumerate(
        chain(fi_tagging.iter_tags(), zh_tagging.iter_tags())
    ):
        tag.id = id

    add_supports(fi_tagging, zh_tagging, align)
    return fi_tagging, zh_tagging


def tag_hollywood():
    fi_tok = "Hollywoodiin"
    zh_tok = "好莱坞"
    zh_untok = "好莱坞"
    align = WordAlignment("0-0")

    return tag(fi_tok, zh_tok, zh_untok, align)


def test_multiple_best_lemmas():
    fi_tagging, zh_tagging = tag_hollywood()

    hollywoodiin = fi_tagging.tokens[0]

    supported = 0
    unsupported = 0
    for tag in hollywoodiin.tags:
        if len(tag.supports):
            supported += 1
            assert len(tag.supports) == 1
            assert tag.supports[0].transfer_type == "aligned"
        else:
            unsupported += 1
    assert supported == 2
    assert unsupported == 3


def tag_hyva_ystavani_alan():
    fi_tok = "Hyvä ystäväni Alan ."
    zh_tok = "我 的 朋友 ， 阿兰 ..."
    zh_untok = "我的朋友，阿兰..."

    align = WordAlignment("0-0 0-1 1-2 2-4 3-5")

    return tag(fi_tok, zh_tok, zh_untok, align)


def test_hyva_ystavani_alan_support_alignment():
    fi_tagging, zh_tagging = tag_hyva_ystavani_alan()

    ystavani_tok = fi_tagging.tokens[1]
    correct_tag = None
    for tag in ystavani_tok.tags:
        for lang, lemma_obj in tag.lemma_objs:
            synset_lemmas = lemma_obj.synset().lemmas()
            if (
                lang == "fin"
                and len(synset_lemmas) == 1
                and synset_lemmas[0].name() == "friend"
            ):
                correct_tag = tag
    assert correct_tag is not None
    assert any((support.transfer_type == "aligned" for support in correct_tag.supports))
