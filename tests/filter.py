from lxml import etree
from string import Template

from stiff.filter import AlignTournament, HasSupportTournament, decode_dom_arg

ALIGNED_SUPPORT = "transfer-type=aligned&amp;transfer-from=3&amp;transform-chain=%5B%5D"
UNALIGNED_SUPPORT = (
    "transfer-type=unaligned&amp;transfer-from=10&amp;transform-chain=%5B%27deriv%27%5D"
)

FILTER_ALIGN_DOM_TEST_CORPUS = Template(
    """
<sentence id="33">
<text id="zh-tok" lang="zh">谋杀 ！</text>
<text id="zh-untok" lang="zh" tokenized="false">谋杀！</text>
<text id="fi-tok" lang="fi">Murha !</text>
<gram type="finnpos" for="fi-tok"><![CDATA[[["murha", {"pos": "NOUN", "num": "SG", "case": "NOM"}], ["!", {"pos": "PUNCTUATION"}]]]]></gram>
<annotations>
$annotations
</annotations>
</sentence>
"""
)

ANNOTATION_MURHA_0 = Template(
    """
<annotation id="0" type="stiff"$support rank="1" freq="1247400" lang="fi" anchor="Murha" anchor-positions="from-id=fi-tok&amp;char=0&amp;token=0&amp;token-length=1" lemma="murha" wnlemma="murha" wordnets="fin qwf qf2" lemma-path="omor,recurs,finnpos">murder.n.01 murha.n.02</annotation>
"""
)

ANNOTATION_MURHA_1 = Template(
    """
<annotation id="1" type="stiff"$support rank="2" freq="13860" lang="fi" anchor="Murha" anchor-positions="from-id=fi-tok&amp;char=0&amp;token=0&amp;token-length=1" lemma="murha" wnlemma="murha" wordnets="fin qf2" lemma-path="omor,recurs,finnpos">bloodshed.n.01 murha.n.01</annotation>
"""
)

ANNOTATION_MURHA_0_BOTH = ANNOTATION_MURHA_0.substitute(
    {"support": f' support="{ALIGNED_SUPPORT} {UNALIGNED_SUPPORT}"'}
)

ANNOTATION_MURHA_1_ALIGNED = ANNOTATION_MURHA_1.substitute(
    {"support": f' support="{ALIGNED_SUPPORT}"'}
)

ANNOTATION_MURHA_1_UNALIGNED = ANNOTATION_MURHA_1.substitute(
    {"support": f' support="{UNALIGNED_SUPPORT}"'}
)

ANNOTATION_MURHA_1_NO_SUPPORT = ANNOTATION_MURHA_1.substitute({"support": ""})


def test_filter_align_dom():
    tournament = AlignTournament(*decode_dom_arg("dom"))
    # If we have two annotations, one with aligned/unaligned and one with
    # aligned, neither should dominate
    sent1 = etree.fromstring(
        FILTER_ALIGN_DOM_TEST_CORPUS.substitute(
            {
                "annotations": "".join(
                    [ANNOTATION_MURHA_0_BOTH, ANNOTATION_MURHA_1_ALIGNED]
                )
            }
        )
    )
    tournament.proc_sent(sent1)
    assert len(sent1.xpath("//annotation")) == 2

    # If we have two annotations, one with aligned/unaligned and one with
    # unaligned, the first should dominate
    sent2 = etree.fromstring(
        FILTER_ALIGN_DOM_TEST_CORPUS.substitute(
            {
                "annotations": "".join(
                    [ANNOTATION_MURHA_0_BOTH, ANNOTATION_MURHA_1_UNALIGNED]
                )
            }
        )
    )
    tournament.proc_sent(sent2)
    assert len(sent2.xpath("//annotation")) == 1
    assert len(sent2.xpath("//annotation[@id='0']")) == 1


def test_filter_has_support():
    tournament = HasSupportTournament(*decode_dom_arg("dom"))
    # If we have two annotations and one has no support, the one with support
    # dominates
    sent1 = etree.fromstring(
        FILTER_ALIGN_DOM_TEST_CORPUS.substitute(
            {
                "annotations": "".join(
                    [ANNOTATION_MURHA_0_BOTH, ANNOTATION_MURHA_1_NO_SUPPORT]
                )
            }
        )
    )
    tournament.proc_sent(sent1)
    assert len(sent1.xpath("//annotation")) == 1
    assert len(sent1.xpath("//annotation[@id='0']")) == 1

    # If we have two annotations and both have support, neither dominates
    sent2 = etree.fromstring(
        FILTER_ALIGN_DOM_TEST_CORPUS.substitute(
            {
                "annotations": "".join(
                    [ANNOTATION_MURHA_0_BOTH, ANNOTATION_MURHA_1_ALIGNED]
                )
            }
        )
    )
    tournament.proc_sent(sent2)
    assert len(sent2.xpath("//annotation")) == 2
