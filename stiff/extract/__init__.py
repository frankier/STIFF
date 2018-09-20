from typing import Any, Dict, Type

from .cmn import CmnExtractor
from .fin import FinExtractor

__all__ = ["CmnExtractor", "FinExtractor", "get_extractor"]


_registry: Dict[str, Type] = {}


def get_extractor(name: str) -> Any:
    if name not in _registry:
        extractor_cls = globals()[name]
        _registry[name] = extractor_cls()
    return _registry[name]
