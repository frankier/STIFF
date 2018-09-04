from abc import ABC, abstractmethod
from typing import Dict, List, Tuple
from nltk.corpus.reader import Lemma


class ExtractableWordnet(ABC):
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
    def lemma_keys(lemma: str) -> List[List[Tuple[str, Lemma]]]:
        pass
