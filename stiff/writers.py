from xml.sax.saxutils import quoteattr
from nltk.corpus.reader.wordnet import Synset, WordNetError
from stiff.tagging import Token, TaggedLemma
from typing import Tuple  # noqa: F401
from typing import Optional, List


def ann_common_attrs(lang: str, tok: Token, tag: TaggedLemma) -> str:
    anchor_positions = [anchor.urlencode() for anchor in tok.anchors]
    attrs = (
        ("lang", lang),
        ("anchor", tok.token),
        ("anchor-positions", " ".join(anchor_positions)),
        ("lemma", tag.lemma),
        ("wnlemma", " ".join(tag.lemma_names)),
        ("wordnets", " ".join((tag.wordnets))),
    )  # type: Tuple[Tuple[str, str], ...]
    return (
        " ".join(
            "{}={}".format(k, quoteattr(v))
            for k, v in attrs
        )
        + " "
    )


def ann_text(tag: TaggedLemma) -> str:
    bits = list(tag.synset_names)
    wn_to_synset_name = dict(tag.wn_synset_names)
    if "qf2" in wn_to_synset_name and wn_to_synset_name["qf2"] in bits:
        qf2_lemma = wn_to_synset_name["qf2"]
        bits.remove(qf2_lemma)
        bits.append(qf2_lemma)
    return " ".join(bits)


def maybe_fi2en_ss(ss: Synset) -> Optional[Synset]:
    from finntk.wordnet.reader import get_en_fi_maps
    from finntk.wordnet.utils import ss2pre, pre2ss
    from nltk.corpus import wordnet
    fi2en, _en2fi = get_en_fi_maps()
    pre_fi = ss2pre(ss)
    pre_en = fi2en.get(pre_fi)
    if pre_en is None:
        return None
    try:
        return pre2ss(wordnet, pre_en)
    except WordNetError:
        return None


def related_lemma_list(tag: TaggedLemma) -> str:
    synsets = set((lemma_obj.synset() for (wn, lemma_obj) in tag.lemma_objs))
    related_synsets = synsets.copy()
    if len(tag.lemma_objs) == 1:
        wn, lemma_obj = tag.lemma_objs[0]
        if wn == 'qf2':
            extra_ss = maybe_fi2en_ss(lemma_obj.synset())
            if extra_ss:
                related_synsets.add(extra_ss)
    lemma_name_set = {ln for ss in related_synsets for ln in ss.lemma_names()}
    lemma_names = sorted(lemma_name_set)
    return ", ".join(lemma_names)


def preferred_synset(tag: TaggedLemma) -> Synset:
    d = dict(tag.lemma_objs)
    lemma = d.get('fin') or d.get('qf2') or d.get('qwf')
    return lemma.synset()


def man_ann_ann(lang: str, tok: Token, tag: TaggedLemma) -> str:
    def maybe_fmt_list(title: str, synsets: List[Synset]) -> str:
        names = sorted([hyp.name() for hyp in synsets])
        if names:
            return "{}: {}; ".format(title, ", ".join(names))
        return ""

    synset = preferred_synset(tag)
    defn = synset.definition().replace("--", "-")
    return (
        "<annotation "
        'type="man-ann" '
        '{}'
        'lemma-path="whole">'
        "{}</annotation>\n"
        "<!-- {}: {} ({}{}lexname: {}) -->\n"
    ).format(
        ann_common_attrs(lang, tok, tag),
        ann_text(tag),
        related_lemma_list(tag),
        defn,
        maybe_fmt_list("hyp", synset.hypernyms()),
        maybe_fmt_list("root", synset.root_hypernyms()),
        synset.lexname(),
    )


class Writer:
    def __init__(self, outf):
        self.outf = outf
        self.sent_idx = 0

    def __enter__(self):
        self.outf.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.outf.write('<corpus source="OpenSubtitles2018">\n')
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.outf.write("</corpus>\n")
        self.outf.close()

    def begin_subtitle(self, srcs, imdb):
        self.outf.write(
            '<subtitle sources="{}" imdb="{}">\n'.format(" ".join(srcs), imdb)
        )

    def end_subtitle(self):
        self.outf.write("</subtitle>\n")
        self.sent_idx = 0

    def begin_sent(self):
        self.outf.write('<sentence id="{}">\n'.format(self.sent_idx))
        self.sent_idx += 1

    def end_sent(self):
        self.outf.write("</sentence>\n")

    @staticmethod
    def _tok_extra(is_tokenised):
        return ' tokenized="false"' if not is_tokenised else ""

    def write_text(self, lang, text, is_tokenised=True):
        id = "{}-{}tok".format(lang, "" if is_tokenised else "un")
        self.outf.write(
            '<text id="{}" lang="{}"{}>{}</text>\n'.format(
                id, lang, self._tok_extra(is_tokenised), text
            )
        )

    def write_ann(self, lang: str, tok: Token, tag: TaggedLemma):
        supports = [support.urlencode() for support in tag.supports]

        if len(supports):
            support_attr = "support={} ".format(quoteattr(" ".join(supports)))
        else:
            support_attr = ""

        if tag.rank is not None:
            freq_attrs = "rank={} freq={} ".format(
                quoteattr(str(tag.rank[0])), quoteattr(str(tag.rank[1]))
            )
        else:
            freq_attrs = ""

        self.outf.write(
            (
                "<annotation "
                'id="{}" '
                'type="stiff" '
                "{}{}{}"
                'lemma-path="whole">'
                "{}</annotation>\n"
            ).format(
                tag.id,
                support_attr,
                freq_attrs,
                ann_common_attrs(lang, tok, tag),
                ann_text(tag),
            )
        )

    def start_anns(self):
        self.outf.write("<annotations>\n")

    def end_anns(self):
        self.outf.write("</annotations>\n")


class AnnWriter(Writer):
    def begin_subtitle(self, srcs, imdb):
        self.srcs = srcs
        self.imdb = imdb

    def end_subtitle(self):
        pass

    def inc_sent(self):
        self.sent_idx += 1

    def begin_sent(self):
        self.outf.write(
            '<sentence id="{}">\n'.format(
                "{}; {}; {}".format(" ".join(self.srcs), self.imdb, self.sent_idx)
            )
        )

    def write_ann(self, lang: str, tok: Token, tag: TaggedLemma):
        self.outf.write(man_ann_ann(lang, tok, tag))
