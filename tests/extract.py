from stiff.extract import extract_full_cmn, extract_full_fin
import stiff.fixes  # noqa


def _filter_toks(tagging, needle):
    return [
        token
        for token in tagging.tokens
        if any((
            lemma_obj.name() == needle
            for tag in token.tags
            for (_wn, lemma_obj) in tag.lemma_objs))
    ]


def test_extract_fin_saada_aikaan():
    tagging = extract_full_fin("Katso , mitä olet saanut aikaan .")
    saada_aikaan_tokens = _filter_toks(tagging, "saada_aikaan")
    assert len(saada_aikaan_tokens) >= 1


def test_extract_fin_ei_koskaan():
    tagging = extract_full_fin("Älä koskaan sano mitään tuollaista hänestä !")
    ei_koskaan_tokens = _filter_toks(tagging, "ei_koskaan")
    assert 1 <= len(ei_koskaan_tokens) <= 2


def test_extract_zh_hollywood():
    zh_tok = "好莱坞"
    zh_untok = "好莱坞"
    zh_tagging = extract_full_cmn(zh_untok, zh_tok)
    matching_token = None
    for tok in zh_tagging.tokens:
        if tok.token == "好莱坞":
            matching_token = tok
    assert matching_token is not None
    assert len(matching_token.anchors) == 2
    assert len(matching_token.tags) == 2
    # XXX: Assert one is cmn, one qwc?


def test_extract_zh_sincere_congrats_dave():
    zh_tok = "真诚地 ， 大卫 。 恭喜 你 。"
    zh_untok = "真诚地，大卫。 恭喜你。"
    extract_full_cmn(zh_untok, zh_tok)
    # XXX: Add some asserts
