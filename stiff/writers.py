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

    def write_ann(self, lang, anchor, tok, tag):
        supports = [urlencode(support) for support in tag.get("supports", [])]
        anchors = [urlencode(anchor_pos) for anchor_pos in tok["anchors"]]

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
                'lang="{}" '
                'type="stiff" '
                "{}{}"
                "anchor={} "
                "anchor-positions={} "
                "lemma={} "
                "wnlemma={} "
                'wordnets="{}" '
                'lemma-path="{}">'
                "{}</annotation>\n"
            ).format(
                tag["id"],
                lang,
                support_attr,
                freq_attrs,
                quoteattr(anchor),
                quoteattr(" ".join(anchors)),
                quoteattr(tag["lemma"]),
                quoteattr(tag["wnlemma"]),
                tag["synset"][0],
                "whole",
                tag["synset"][1],
            )
        )

    def start_anns(self):
        self.outf.write("<annotations>\n")

    def end_anns(self):
        self.outf.write("</annotations>\n")
