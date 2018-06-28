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

        self.outf.write(
            (
                "<annotation "
                'id="{}" '
                'lang="{}" '
                'type="stiff" '
                "support={} "
                "anchor={} "
                "anchor-positions={} "
                "lemma={} "
                'wordnets="{}" '
                'lemma-path="{}">'
                "{}</annotation>\n"
            ).format(
                tag["id"],
                lang,
                quoteattr(" ".join(supports)),
                quoteattr(anchor),
                quoteattr(" ".join(anchors)),
                quoteattr(tag["lemma"]),
                " ".join(tag["wordnet"]),
                "whole",
                tag["wnlemma"][0],
            )
        )

    def start_anns(self):
        self.outf.write("<annotations>\n")

    def end_anns(self):
        self.outf.write("</annotations>\n")
