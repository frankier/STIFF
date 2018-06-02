from lxml import etree
from xml.sax.saxutils import quoteattr


def free_elem(elem):
    # It's safe to call clear() here because no descendants will be
    # accessed
    elem.clear()
    # Also eliminate now-empty references from the root node to elem
    for ancestor in elem.xpath("ancestor-or-self::*"):
        while ancestor.getprevious() is not None:
            del ancestor.getparent()[0]


def fast_iter(context):
    """
    http://lxml.de/parsing.html#modifying-the-tree
    Based on Liza Daly's fast_iter
    http://www.ibm.com/developerworks/xml/library/x-hiperfparse/
    See also http://effbot.org/zone/element-iterparse.htm
    """
    for event, elem in context:
        yield elem
        free_elem(elem)
    del context


def open_tag(elem):
    return "<{} {}>".format(
        elem.tag, " ".join("{}={}".format(k, quoteattr(v)) for k, v in elem.items())
    )


def close_tag(elem):
    return "</{}>".format(elem.tag)


def transform_sentences(inf, transformer, outf):
    stream = etree.iterparse(inf, events=("start", "end"))
    transform(stream, "sentence", transformer, outf)


def transform(stream, needle_tag, transformer, outf):
    outf.write(b"<?xml version='1.0' encoding='UTF-8'?>\n")

    def outside(event, elem):
        if event == "start":
            outf.write(open_tag(elem).encode("utf-8"))
            outf.write(b"\n")
        else:
            outf.write(close_tag(elem).encode("utf-8"))
            outf.write(b"\n")

    def inside(elem):
        transformer(elem)
        outf.write(etree.tostring(elem, encoding="utf-8"))

    chunk_stream_iter(stream, needle_tag, outside, inside)


def iter_sentences(inf, cb):
    stream = etree.iterparse(inf, events=("start", "end"))
    chunk_iter(stream, "sentence", cb)


def chunk_stream_iter(stream, needle_tag, outside_cb, inside_cb):
    inside = False
    for event, elem in stream:
        if event == "start" and elem.tag == needle_tag:
            inside = True
        if not inside:
            outside_cb(event, elem)
        if event == "end" and elem.tag == needle_tag:
            inside = False
            inside_cb(elem)
            free_elem(elem)


def chunk_iter(stream, needle_tag, inside_cb):
    return chunk_stream_iter(stream, needle_tag, lambda x, y: None, inside_cb)
