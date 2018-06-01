import os
import opencc


_opencc = None


def get_opencc():
    global _opencc
    if _opencc is None:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        opencc_config = os.path.join(dir_path, "../t2s_char.json")
        _opencc = opencc.OpenCC(opencc_config)
    return _opencc
