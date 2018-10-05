from finntk.finnpos import sent_finnpos
from typing import IO, List

from .utils import transform_senseval_contexts


def finnpos_senseval(inf: IO, outf: IO):
    def fmt_analy(analy) -> str:
        surf, lemma, tags = analy
        return "{}|LEM|{}|POS|{}".format(surf, lemma, tags["pos"])

    def tag_tokens(sent: List[str]) -> List[str]:
        analysed = sent_finnpos(sent)
        return [fmt_analy(ana) for ana in analysed]

    transform_senseval_contexts(inf, tag_tokens, outf)
