from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Callable, Iterable
from nltk.corpus.reader import Lemma
from finntk.wordnet.utils import ss2pre


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

    @classmethod
    def synset_group_lemmas(
        cls, wordnet_lemmas: Dict[str, List[Lemma]]
    ) -> Iterable[List[Tuple[str, Lemma]]]:
        from .utils import synset_group_lemmas

        return synset_group_lemmas(wordnet_lemmas, cls)

    @classmethod
    def canonical_synset_id(cls, wn: str, lemma_obj: Lemma) -> str:
        def default_mapper(lemma_obj: Lemma) -> str:
            return ss2pre(lemma_obj.synset())

        return cls._synset_mappers.get(wn, default_mapper)(lemma_obj)
