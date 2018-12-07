from stiff.extract import get_extractor
from stiff.data.fixes import fix_all


fix_all()


def _filter_toks(tagging, needle):
    return [
        token
        for token in tagging.tokens
        if any(
            (
                lemma_obj.name() == needle
                for tag in token.tags
                for (_wn, lemma_obj) in tag.lemma_objs
            )
        )
    ]


def test_extract_fin_saada_aikaan():
    tagging = get_extractor("FinExtractor").extract("Katso , mitä olet saanut aikaan .")
    saada_aikaan_tokens = _filter_toks(tagging, "saada_aikaan")
    assert len(saada_aikaan_tokens) >= 1


def test_extract_fin_ei_koskaan():
    tagging = get_extractor("FinExtractor").extract(
        "Älä koskaan sano mitään tuollaista hänestä !"
    )
    ei_koskaan_tokens = _filter_toks(tagging, "ei_koskaan")
    assert 1 <= len(ei_koskaan_tokens) <= 2


def test_extract_zh_hollywood():
    zh_tok = "好莱坞"
    zh_untok = "好莱坞"
    zh_tagging = get_extractor("CmnExtractor").extract(zh_untok, zh_tok)
    matching_token = None
    for tok in zh_tagging.tokens:
        if tok.token == "好莱坞":
            matching_token = tok
    assert matching_token is not None
    assert len(matching_token.anchors) == 2
    assert len(matching_token.tags) == 2
    # XXX: Assert one is cmn, one qwc?


def sincere_asserts(tagging):
    tokens = []
    for tok in tagging.tokens:
        if len(tok.token) == 3:
            tokens.append(tok)
    assert len(tokens) == 1
    tags = tokens[0].tags
    lemma_objs = [lemma_obj for tag in tags for _lang, lemma_obj in tag.lemma_objs]
    assert len(lemma_objs) >= 4


def test_extract_zh_tok_sincere():
    zh_tok = "真诚地"
    tagging = get_extractor("CmnExtractor").extract_tok(zh_tok)
    sincere_asserts(tagging)


def test_extract_zh_untok_sincere():
    zh_untok = "真诚地"
    tagging = get_extractor("CmnExtractor").extract_untok(zh_untok)
    sincere_asserts(tagging)


def test_extract_zh_sincere_congrats_dave():
    zh_tok = "真诚地 ， 大卫 。 恭喜 你 。"
    zh_untok = "真诚地，大卫。 恭喜你。"
    get_extractor("CmnExtractor").extract(zh_untok, zh_tok)
    # XXX: Add some asserts


def test_hyvaa():
    tagging = get_extractor("FinExtractor").extract("Hyvää !")
    matching_token = None
    wordnet_counts = {"fin": 0, "qf2": 0, "qwf": 0}
    for tok in tagging.tokens:
        if tok.token == "Hyvää":
            matching_token = tok
    assert matching_token is not None
    for tag in matching_token.tags:
        for wn, _ in tag.lemma_objs:
            wordnet_counts[wn] += 1
    assert wordnet_counts["fin"] >= 27
    assert wordnet_counts["qf2"] >= 25
    assert wordnet_counts["qwf"] >= 7
