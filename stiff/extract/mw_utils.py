from typing import Set, Iterable


def chr_to_maybe_space(chr: str, lfs: Iterable[str]) -> Set[str]:
    res = set()
    for lf in lfs:
        res.add(lf.replace(chr, ""))
        res.add(lf.replace(chr, " "))
    return res


def chrs_to_maybe_space(chrs: Iterable[str], lf: str) -> Set[str]:
    res = {lf}
    for chr in chrs:
        res |= chr_to_maybe_space(chr, res)
    return res


def multiword_variants(lf: str) -> Set[str]:
    return chrs_to_maybe_space(["_", "+", " "], lf)
