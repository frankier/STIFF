import opencc

from stiff.data import get_data_path


_opencc = None


def get_opencc():
    global _opencc
    if _opencc is None:
        opencc_config = get_data_path("t2s_char.json")
        _opencc = opencc.OpenCC(opencc_config)
    return _opencc
