from stiff.extract import extract_full_fin
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
