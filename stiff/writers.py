from xml.sax.saxutils import quoteattr
from urllib.parse import urlencode


class Writer:
    def __init__(self, outf):
        self.outf = outf
        self.sent_idx = 0

    def __enter__(self):
        self.outf.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.outf.write('<corpus source="OpenSubtitles2018">\n')
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.outf.write("</corpus>")
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

    def ann_common_attrs(self, lang, anchor, tok, tag):
        anchors = [urlencode(anchor_pos) for anchor_pos in tok["anchors"]]
        return (
            " ".join(
                "{}={}".format(k, quoteattr(v))
                for k, v in (
                    ("lang", lang),
                    ("anchor", anchor),
                    ("anchor-positions", " ".join(anchors)),
                    ("lemma", tag["lemma"]),
                    ("wnlemma", " ".join(set(tag["wnlemma"]))),
                    ("wordnets", " ".join((ss[0] for ss in tag["synset"]))),
                )
            )
            + " "
        )

    def ann_text(self, tag):
        bits = set((ss[1] for ss in tag["synset"]))
        bits = list(bits)
        wn_to_lemma = dict(tag["synset"])
        if "qf2" in wn_to_lemma and wn_to_lemma["qf2"] in bits:
            qf2_lemma = wn_to_lemma["qf2"]
            bits.remove(qf2_lemma)
            bits.append(qf2_lemma)
        return " ".join(bits)

    def write_ann(self, lang, anchor, tok, tag):
        supports = [urlencode(support) for support in tag.get("supports", [])]

        if len(supports):
            support_attr = "support={} ".format(quoteattr(" ".join(supports)))
        else:
            support_attr = ""

        if "rank" in tag:
            freq_attrs = "rank={} freq={} ".format(
                quoteattr(str(tag["rank"][0])), quoteattr(str(tag["rank"][1]))
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
                tag["id"],
                support_attr,
                freq_attrs,
                self.ann_common_attrs(lang, anchor, tok, tag),
                self.ann_text(tag),
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

    def write_ann(self, lang, anchor, tok, tag):
        synsets = set((lo.synset() for lo in tag["lemma_obj"]))
        syn_list = ", ".join(ln for ss in synsets for ln in ss.lemma_names())
        synset = synsets.pop()
        defn = synset.definition()
        self.outf.write(
            (
                "<annotation "
                'type="man-ann" '
                'lemma-path="whole" {}>'
                "{}</annotation>\n"
                "<!-- {}: {} -->\n"
            ).format(
                self.ann_common_attrs(lang, anchor, tok, tag),
                self.ann_text(tag),
                syn_list,
                defn,
            )
        )
