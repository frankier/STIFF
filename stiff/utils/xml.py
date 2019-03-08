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
        abort = False

        def cb(x):
            q.put(x)
            q.join()
            if abort:
                raise Exception("Aborting thread")

        def task(*args, **kwargs):
            f(*(args + (cb,)), **kwargs)
            q.put(job_done)

        thread = Thread(target=task, args=args, kwargs=kwargs)
        thread.start()

        try:
            while True:
                next_item = q.get(True)
                if next_item is job_done:
                    break
                yield next_item
                q.task_done()
        finally:
            abort = True
            try:
                q.task_done()
            except ValueError:
                pass
            thread.join(5)

    return iter


def cb_blocks(block):
    def inner(inf, cb):
        if isinstance(inf, etree.iterparse):
            stream = inf
        else:
            stream = etree.iterparse(inf, events=("start", "end"))
        chunk_cb(stream, eq_matcher(block), cb)

    return inner


cb_sentences = cb_blocks("sentence")


def iter_blocks(block):
    return cb_to_iter(cb_blocks(block))


iter_sentences = iter_blocks("sentence")


def iter_sent_to_pairs(sent_iter):
    for sent in sent_iter:
        yield sent.attrib["id"], sent


def iter_sentences_opensubs18_stream(stream):
    def sentence_chunker(cb):
        chunk_cb(stream, eq_matcher("sentence"), cb)

    for event, element in stream:
        if event == "start" and element.tag == "subtitle":
            sources = " ".join(element.attrib["sources"].split("; "))
            imdb = element.attrib["imdb"]
            for sent in cb_to_iter(sentence_chunker)():
                yield (sources, imdb, sent.attrib["id"]), sent


def iter_sentences_opensubs18(fp):
    stream = etree.iterparse(fp, events=("start", "end"))
    return iter_sentences_opensubs18_stream(stream)


def format_opensubs_id(bits):
    sources, imdb, sent_id = bits
    return "{}; {}; {}".format(sources, imdb, sent_id)


def iter_sentence_id_pairs(fp):
    """
    Like iter_sentences(...), but returns also sentence IDs, in the case of
    OpenSubtitles2018 adjusted to include also subtitle information.
    """
    # Detect OpenSubtitles2018
    stream = etree.iterparse(fp, events=("start", "end"))
    opensubs18 = None
    for idx, (event, element) in zip(range(100), stream):
        if element.tag == "corpus":
            opensubs18 = element.attrib["source"] == "OpenSubtitles2018"
            break
    else:
        assert False, "No <corpus ...> tag found."
    if opensubs18:
        for bits, sent in iter_sentences_opensubs18_stream(stream):
            yield format_opensubs_id(bits), sent
    else:
        for pair in iter_sent_to_pairs(iter_sentences(stream)):
            yield pair


def chunk_stream_cb(stream, matcher: Matcher, outside_cb, inside_cb, always_cb=None):
    inside = False
    depth = 0
    for event, elem in stream:
        if event == "start":
            depth += 1
        if event == "end":
            depth -= 1
        if depth < 0:
            return
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
