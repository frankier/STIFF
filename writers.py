class UnifiedWriter:
    def __init__(self, fn):
        self.fn = fn
        self.idx = 0

    def __enter__(self):
        self.outxml = open(fn + '.data.xml', 'w')
        self.outkey = open(fn + '.gold.key.txt', 'w')
        self.outxml.write('<?xml version="1.0" encoding="UTF-8" ?>')
        self.outxml.write('<corpus lang="en" source="semcor">')

    def text(self, id_, source):
        self.outxml.write('<text id="d000" source="br-e30">')
        yield
        self.outxml.write('</text>')

    def __exit__(self):
        self.outxml.close()
        self.outkey.close()

    def write_sent(self, sent, synsets):
        pass


class EuroSenseWriter:
    def __init__(self, fn):
        self.fn = fn
        self.idx = 0

    def __enter__(self):
        self.outf = open(fn, 'w')
        self.outf.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.outf.write('<corpus source="europarl">\n')

    def __exit__(self):
        self.outf.write('</corpus>')
        self.outf.close()

    def write_sent(self, sent, synsets):
        self.outf.write('<sentence id="0">')
        self.outf.write('<text lang="fi">{}</text>'.format(sent))
        self.outf.write('<annotations>')
        self.outf.write('<annotation lang="fi" type="BABELFY" anchor="tärkeää" lemma="tärkeä" coherenceScore="0.1348" nasariScore="--"></annotation>')
        self.outf.write('</annotations>')
        self.outf.write('</sentence>')
