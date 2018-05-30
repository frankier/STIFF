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
        id = "{}-{}tok".format(lang, "" if is_tokenised else "un")
        self.outf.write('<text id="{}" lang="{}"{}>{}</text>\n'.format(id, lang, self._tok_extra(is_tokenised), text))

    def write_ann(self, lang, anchor, tok, tag):
        supports = []
        for support in tag.get('support', []):
            support_bits = [support['type'], 'from', str(support['source'])]
            if 'preproc' in support:
                support_bits.append('preproc')
                support_bits.extend(support['preproc'])
            supports.append(":".join(support_bits))
        anchors = []

        for anchor_pos in tok['anchors']:
            anchor_text = "from:{}".format(anchor_pos['id'])
            if 'char' in anchor_pos:
                anchor_text += ";char:{}".format(anchor_pos['char'])
            if 'token' in anchor_pos:
                anchor_text += ";token:{}".format(anchor_pos['token'])
            anchors.append(anchor_text)

        #lemma_path = "from:XXX:chars:YY;from:XX2 {}".format(anchor_pos)
        self.outf.write(
            ('<annotation '
             'id="{}" '
             'lang="{}" '
             'type="stiff" '
             'support="{}" '
             'anchor="{}" '
             'anchor-positions="{}" '
             'lemma="{}" '
             'wordnets="{}" '
             'lemma-path="{}">'
             '{}</annotation>\n')
            .format(
                tag['id'],
                lang,
                " ".join(supports),
                anchor,
                " ".join(anchors),
                tag['lemma'],
                " ".join(tag['wordnet']),
                "whole",
                tag['wnlemma'][0])
            )
