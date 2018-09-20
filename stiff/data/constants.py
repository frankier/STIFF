def invert(d):
    return {v: k for k, v in d.items()}


WN_UNI_POS_MAP = {"n": "NOUN", "v": "VERB", "a": "ADJ", "r": "ADV"}
UNI_POS_WN_MAP = invert(WN_UNI_POS_MAP)
DEFAULT_SAMPLE_LINES = list(range(17, 1000, 25))
assert len(DEFAULT_SAMPLE_LINES) == 40
DEFAULT_SAMPLE_MAX = 1000
