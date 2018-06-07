from lxml import etree
from xml.sax.saxutils import quoteattr, escape
from functools import partial


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
    attrs = elem.items()
    if not len(attrs):
        return "<{}>".format(elem.tag)
    return "<{} {}>".format(
        elem.tag, " ".join("{}={}".format(k, quoteattr(v)) for k, v in attrs)
    )


def close_tag(elem):
    return "</{}>".format(elem.tag)


def transform_blocks(block, inf, transformer, outf):
    stream = etree.iterparse(inf, events=("start", "end"))
    transform(stream, block, transformer, outf)


transform_sentences = partial(transform_blocks, "sentence")


def transform(stream, needle_tag, transformer, outf):
    outf.write(b"<?xml version='1.0' encoding='UTF-8'?>\n")

    missing_text = False

    def always(event, elem):
        nonlocal missing_text

        if missing_text:
            if event == "end":
                prev_elem = elem
            else:
                prev_elem = elem.getparent()
            if prev_elem.text is not None:
                outf.write(escape(prev_elem.text).encode("utf-8"))
            missing_text = False

    def outside(event, elem):
        nonlocal missing_text

        if event == "start":
            outf.write(open_tag(elem).encode("utf-8"))
            missing_text = True
        else:
            outf.write(close_tag(elem).encode("utf-8"))
            if elem.tail is not None:
                outf.write(elem.tail.encode("utf-8"))

    def inside(elem):
        bypass = transformer(elem)
        if not bypass:
            outf.write(etree.tostring(elem, encoding="utf-8"))

    chunk_stream_cb(stream, needle_tag, outside, inside, always)


def cb_to_iter(f):
    def iter(*args, **kwargs):
        from threading import Thread
        from queue import Queue

        q = Queue()
        job_done = object()

        def cb(x):
            q.put(x)
            q.join()

        def task(*args, **kwargs):
            f(*(args + (cb,)), **kwargs)
            q.put(job_done)

        thread = Thread(target=task, args=args, kwargs=kwargs)
        thread.start()

        while True:
            next_item = q.get(True)
            if next_item is job_done:
                break
            yield next_item
            q.task_done()
        thread.join()

    return iter


def cb_sentences(inf, cb):
    stream = etree.iterparse(inf, events=("start", "end"))
    chunk_cb(stream, "sentence", cb)


iter_sentences = cb_to_iter(cb_sentences)


def chunk_stream_cb(stream, needle_tag, outside_cb, inside_cb, always_cb=None):
    inside = False
    for event, elem in stream:
        if event == "start" and elem.tag == needle_tag:
            inside = True
        if always_cb is not None:
            always_cb(event, elem)
        if not inside:
            outside_cb(event, elem)
        if event == "end" and elem.tag == needle_tag:
            inside = False
            inside_cb(elem)
            free_elem(elem)


def chunk_cb(stream, needle_tag, inside_cb):
    return chunk_stream_cb(stream, needle_tag, lambda x, y: None, inside_cb)