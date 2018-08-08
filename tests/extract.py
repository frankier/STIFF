from stiff.extract import get_synset_set_fin
import stiff.fixes  # noqa


def test_extract_fin():
    tagging = get_synset_set_fin("Katso, mitä olet saanut aikaan.")
    saada_aikaan_tokens = [
        token for token in tagging.tokens if token["wnlemma"] == "saada_aikaan"
    ]
    assert len(saada_aikaan_tokens) >= 1
