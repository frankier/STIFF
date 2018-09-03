import re
from os.path import join as pjoin


CHINESES = ["zh_cn", "zh_tw"]


class RealignException(Exception):
    pass


class SkippedTooMuchException(RealignException):
    pass


class TokLineEndedFirstException(RealignException):
    pass


def realign(untok, tok, skiplimit=200):
    untok_line = untok.readline()
    tok_line = tok.readline()
    skipped = 0
    while 1:
        tok_line_nospace = re.sub(r"\s", "", tok_line)
        untok_line_nospace = re.sub(r"\s", "", untok_line)
        if tok_line_nospace != untok_line_nospace:
            skipped += 1
        else:
            yield untok_line, tok_line
            tok_line = tok.readline()
            skipped = 0
        untok_line = untok.readline()
        if tok_line == "":
            if untok_line == "":
                return
            else:
                raise TokLineEndedFirstException()
        if skipped > skiplimit:
            raise SkippedTooMuchException()


def read_opensubtitles2018(dir):
    for zh in CHINESES:
        pair = "fi-{}".format(zh)
        pair_dir = pjoin(dir, pair)

        zh_tok_f = open(pjoin(pair_dir, "c.clean." + zh))
        fi_tok_f = open(pjoin(pair_dir, "c.clean.fi"))
        zh_untok_f = open(pjoin(pair_dir, "OpenSubtitles2018.{}.{}".format(pair, zh)))
        alignment_f = open(pjoin(pair_dir, "aligned.grow-diag-final-and"))
        ids_f = open(pjoin(pair_dir, "ids"))

        prev_imdb_id = None
        for idx, ((zh_untok, zh_tok), fi_tok, line_id, moses_alignment) in enumerate(
            zip(realign(zh_untok_f, zh_tok_f), fi_tok_f, ids_f, alignment_f)
        ):
            src = get_src(line_id)
            srcs, imdb_id = src[:-1], src[-1]
            align = WordAlignment(moses_alignment[:-1])
            yield idx, zh_untok[:-1], zh_tok[:-1], fi_tok[
                :-1
            ], srcs, imdb_id, prev_imdb_id != imdb_id, align
            prev_imdb_id = imdb_id


def get_src(line_id):
    bits = line_id.split()
    lang1_src = bits[0]
    lang2_src = bits[1]
    imdb1 = lang1_src.split("/")[2]
    imdb2 = lang2_src.split("/")[2]
    assert imdb1 == imdb2
    return (lang1_src, lang2_src, imdb1)


class WordAlignment:
    def __init__(self, alignment):
        self.s2t = {}
        self.t2s = {}
        if not alignment:
            return
        for align in alignment.split(" "):
            s, t = [int(n) for n in align.split("-")]
            self.s2t[s] = t
            self.t2s[t] = s
