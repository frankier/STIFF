class Writer:
    def __init__(self, fn):
        self.fn = fn
        self.sent_idx = 0

    def __enter__(self):
        self.outf = open(self.fn, 'w')
        self.outf.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.outf.write('<corpus source="europarl">\n')
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.outf.write('</corpus>')
        self.outf.close()

    def begin_subtitle(self, srcs, imdb):
        self.outf.write('<subtitle sources="{}" imdb="{}">\n'.format("; ".join(srcs), imdb))

    def end_subtitle(self):
        self.outf.write('</subtitle>\n')
        self.sent_idx = 0

    def begin_sent(self):
        self.outf.write('<sentence id="{}">\n'.format(self.sent_idx))
        self.sent_idx += 1

    def end_sent(self):
        self.outf.write('</sentence>\n')

    @staticmethod
    def _tok_extra(is_tokenised):
        return " tokenized=\"false\"" if not is_tokenised else ""

    def write_text(self, lang, text, is_tokenised=True):
        self.outf.write('<text lang="{}"{}>{}</text>\n'.format(lang, self._tok_extra(is_tokenised), text))

    def write_ann(self, lang, anchor, anchor_pos, lemma, synset, is_tokenised=True):
        self.outf.write(
            ('<annotation lang="{}" '
             'type="stiff" '
             'anchor="{}" '
             'anchor-pos="{}" '
             'lemma="{}"{}>'
             '{}</annotation>\n')
            .format(
                lang,
                anchor,
                anchor_pos,
                lemma,
                self._tok_extra(is_tokenised),
                synset)
            )
