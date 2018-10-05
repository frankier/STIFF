from io import BytesIO
from lxml import etree


EU_XML = """
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE corpus SYSTEM "lexical-sample.dtd">
<corpus lang="finnish">
<lexelt item="euroopan_unioni.n">
<instance id="xx">
<context>
<head>Euroopan unionin</head> on hyvää .
</context>
</instance>
</lexelt>
</corpus>
""".strip().encode(
    "utf-8"
)


def test_head_doesnt_move():
    """
    Tests that if the <head> is the first thing in the input, it's the first thing in the output.
    """
    from stiff.munge.pos import finnpos_senseval

    inf = BytesIO(EU_XML)
    outf = BytesIO()
    finnpos_senseval(inf, outf)
    result = outf.getvalue()
    tree = etree.fromstring(result)
    assert tree.xpath("//context")[0].text.strip() == ""
