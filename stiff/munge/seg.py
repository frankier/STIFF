from typing import IO, List

from .utils import transform_senseval_contexts


def omorfi_segment_senseval(inf: IO, outf: IO):
    # XXX: we should move any segments after the last of the lemma segment
    # outside of the <head> tag -- might mean transform_senseval_contexts needs
    # to be reworked

    def seg_token(token: str) -> str:
        from finntk.omor.inst import get_omorfi
        from omorfi.token import get_segments

        omorfi = get_omorfi()
        segments = omorfi.segment(token)
        return "→ ←".join(get_segments(segments[0], True, True, True, False, False))

    def seg_tokens(sent: List[str]) -> List[str]:
        return [seg_token(tok) for tok in sent]

    transform_senseval_contexts(inf, seg_tokens, outf)
