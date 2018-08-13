from stiff.extract import get_synset_set_fin
import stiff.fixes  # noqa


def test_extract_fin():
    tagging = get_synset_set_fin("Katso, mitä olet saanut aikaan.")
    saada_aikaan_tokens = [
        token
        for token in tagging.tokens
        if any((tag["wnlemma"] == "saada_aikaan" for tag in token["tags"]))
    ]
    assert len(saada_aikaan_tokens) >= 1
