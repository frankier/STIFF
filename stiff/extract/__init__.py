from .fin import extract_full_fin
from .cmn import extract_full_cmn

__all__ = ["extract_full_fin", "extract_full_cmn", "get_anchor"]


def get_anchor(tok):
    if isinstance(tok["token"], str):
        return tok["token"]
    else:
        return tok["token"]["surf"]
