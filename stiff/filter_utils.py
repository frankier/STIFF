from lxml import etree
from xml.sax.saxutils import quoteattr, escape
from functools import partial
from typing import Callable, IO

Matcher = Callable[[str], bool]
Transformer = Callable[[etree.ElementBase], etree.ElementBase]


def eq_matcher(tag_name: str) -> Matcher:
    def inner(other: str) -> bool:
        return tag_name == other
    return inner


def in_matcher(*tag_names: str) -> Matcher:
    def inner(other: str):
        return other in tag_names
    return inner


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
    return "</{}>{}".format(elem.tag, elem.tail or "\n")


def transform_blocks(matcher: Matcher, inf: IO, transformer: Transformer, outf: IO):
    stream = etree.iterparse(inf, events=("start", "end"))
    transform(stream, matcher, transformer, outf)


transform_sentences = partial(transform_blocks, eq_matcher("sentence"))

BYPASS = object()
BREAK = object()


def write_event(event, elem, outf):
    if event == "start":
        outf.write(open_tag(elem).encode("utf-8"))
        return True
    else:
        outf.write(close_tag(elem).encode("utf-8"))
        return False


def fixup_missing_text(event, elem, outf):
    if event == "end":
        prev_elem = elem
        if len(elem):
            return
    else:
        prev_elem = elem.getparent()
        if prev_elem[0] != elem:
            return
    if prev_elem.text is not None:
        outf.write(escape(prev_elem.text).encode("utf-8"))


def close_all(elem, outf):
    for par_elem in elem.iterancestors():
        outf.write(close_tag(par_elem).encode("utf-8"))


def transform(stream, matcher: Matcher, transformer: Transformer, outf: IO):
    outf.write(b"<?xml version='1.0' encoding='UTF-8'?>\n")

    missing_text = False

    def always(event, elem):
        nonlocal missing_text
        if missing_text:
            fixup_missing_text(event, elem, outf)
            missing_text = False

    def outside(event, elem):
        nonlocal missing_text
        missing_text = write_event(event, elem, outf)

    def inside(elem):
        retval = transformer(elem)
        if retval is BREAK:
            close_all(elem, outf)
            return retval
        if retval is not BYPASS:
            outf.write(etree.tostring(elem, encoding="utf-8"))
        return retval

    chunk_stream_cb(stream, matcher, outside, inside, always)


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
    chunk_cb(stream, eq_matcher("sentence"), cb)


iter_sentences = cb_to_iter(cb_sentences)


def chunk_stream_cb(stream, matcher: Matcher, outside_cb, inside_cb, always_cb=None):
    inside = False
    for event, elem in stream:
        if event == "start" and matcher(elem.tag):
            inside = True
        if always_cb is not None:
            always_cb(event, elem)
        if not inside:
            outside_cb(event, elem)
        if event == "end" and matcher(elem.tag):
            inside = False
            retval = inside_cb(elem)
            free_elem(elem)
            if retval is BREAK:
                break


def chunk_cb(stream, matcher: Matcher, inside_cb):
    return chunk_stream_cb(stream, matcher, lambda x, y: None, inside_cb)
