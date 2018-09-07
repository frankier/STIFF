from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Callable, Iterable
from nltk.corpus.reader import Lemma


class ExtractableWordnet(ABC):
    _synset_mappers: Dict[str, Callable[[Lemma], str]] = {}

    @staticmethod
    @abstractmethod
    def lang() -> str:
        pass

    @staticmethod
    @abstractmethod
    def lemma_names() -> Dict[str, List[str]]:
        pass

    @staticmethod
    @abstractmethod
    def lemma_keys(lemma: str) -> Iterable[List[Tuple[str, Lemma]]]:
        pass

    @classmethod
    def synset_group_lemmas(cls, wordnet_lemmas: Dict[str, List[Lemma]]) -> Iterable[List[Tuple[str, Lemma]]]:
        from .utils import synset_group_lemmas
        return synset_group_lemmas(wordnet_lemmas, cls._synset_mappers)
