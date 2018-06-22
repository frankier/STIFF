def invert(d):
    return {v: k for k, v in d.items()}


WN_UNI_POS_MAP = {"n": "NOUN", "v": "VERB", "a": "ADJ", "r": "ADV"}
UNI_POS_WN_MAP = invert(WN_UNI_POS_MAP)
