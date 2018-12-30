import sys
from lxml import etree
from typing import IO
import click
from stiff.utils.xml import transform_sentences, iter_sentences
import os
from os.path import join as pjoin
from plumbum import local
import click_log
import logging
from collections import Counter

logger = logging.getLogger(__name__)
click_log.basic_config(logger)

python = local[sys.executable]

dir = os.path.dirname(os.path.realpath(__file__))
fix_eurosense_py = pjoin(dir, "fix-eurosense.py")


@click.group("fix-eurosense")
@click_log.simple_verbosity_option(logger)
def fix_eurosense():
    """
    Commands to fix up problems in Eurosense
    """
    pass


def find_word(haystack, needle, cursor=0):
    haystack = " " + haystack + " "
    return haystack.find(" " + needle + " ", cursor)


def count_overlap(haystack, needle):
    count = 0
    start = 0
    while True:
        start = haystack.find(needle, start) + 1
        if start > 0:
            count += 1
        else:
            return count


@fix_eurosense.command("trace")
@click.argument("inf", type=click.File("rb"))
def trace(inf: IO):
    for sent_elem in iter_sentences(inf):
        texts = list(sent_elem.xpath(".//text"))
        anns = list(sent_elem.xpath(f".//annotation"))

        lang_texts = {}
        for text in texts:
            lang = text.attrib["lang"]
            lang_texts[lang] = text

        # Find problem annotations
        for ann_idx, ann in enumerate(anns):
            lang = ann.attrib["lang"]
            text = lang_texts[lang]
            anchor = ann.attrib["anchor"]
            if text.text is None:
                match_pos = -1
            else:
                match_pos = find_word(text.text, anchor)
            if match_pos == -1:
                print(lang, text.text)
                alternatives = []
                for alt_lang, alt_text in lang_texts.items():
                    if alt_text.text is None:
                        continue
                    match_pos = find_word(alt_text.text, anchor)
                    if match_pos != -1:
                        alternatives.append(alt_lang)
                print(
                    "Sent #{}: '{}' not found in {}, could be {}".format(
                        sent_elem.attrib["id"], anchor, lang, " ".join(alternatives)
                    )
                )
                # print(etree.tostring(ann, encoding="unicode"))


@fix_eurosense.command("reorder-cognates")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--order", type=click.Choice(["set", "multiset", "intersect-grow"]))
def reorder_cognates(inf: IO, outf: IO, order):
    reorderings = 0

    def get_lang_order(texts):
        langs = []
        for text in texts:
            lang = text.attrib["lang"]
            langs.append(lang)
        return langs

    def correct_order_multiset(langs, ann_langs):
        correct_order = []
        for lang in langs:
            while ann_langs[lang] > 0:
                correct_order.append(lang)
                ann_langs[lang] -= 1
        return correct_order

    def get_correct_order_set(anchor, texts, anns):
        # Get lang order
        langs = get_lang_order(texts)
        # Gather annotation languages
        ann_langs = set()
        for ann in anns:
            ann_langs.add(ann.attrib["lang"])
        # Put into correct order
        correct_order = []
        for lang in langs:
            if lang in ann_langs:
                correct_order.append(lang)
        return correct_order

    def ann_langs_multiset(anns):
        ann_langs = Counter()
        for ann in anns:
            ann_langs[ann.attrib["lang"]] += 1
        return ann_langs

    def text_anchor_langs_multiset(anchor, texts):
        ann_langs = Counter()
        for text in texts:
            if text.text is None:
                continue
            pad_text = " " + text.text + " "
            pad_anchor = " " + anchor + " "
            ann_langs[text.attrib["lang"]] += count_overlap(pad_text, pad_anchor)
        return ann_langs

    def get_correct_order_multiset(anchor, texts, anns):
        # Get lang order
        langs = get_lang_order(texts)
        # Gather annotation languages
        ann_langs = ann_langs_multiset(anns)
        # Put into correct order
        return correct_order_multiset(langs, ann_langs)

    def get_correct_order_text_intersect_grow(anchor, texts, anns):
        # Get lang order
        langs = get_lang_order(texts)
        # Intersect
        ann_langs = ann_langs_multiset(anns)
        text_anchored_langs = text_anchor_langs_multiset(anchor, texts)
        intersected_langs = ann_langs & text_anchored_langs
        # Grow into extra text anchors
        extra_langs = text_anchored_langs - ann_langs
        target_length = len(anns)
        intersected_anchors = sum(intersected_langs.values())
        extra_anchors = sum(extra_langs.values())
        assert intersected_anchors + extra_anchors >= target_length, (
            f"{intersected_anchors} + {extra_anchors} < {target_length}: Looking for '{anchor}' with {ann_langs} and {text_anchored_langs} in...\n"
            + "\n".join(text.text or "" for text in texts)
        )
        candidate_langs = intersected_langs
        for lang in extra_langs:
            cands = sum(candidate_langs.values())
            logger.debug(f"{cands} {target_length} {candidate_langs}")
            if cands == target_length:
                break
            candidate_langs[lang] += min(
                extra_langs[lang], target_length - sum(candidate_langs.values())
            )
        return correct_order_multiset(langs, candidate_langs)

    def mk_proc_sent(get_ann_langs):
        def proc_sent(sent_elem):
            nonlocal reorderings
            logger.debug("Sentence #{}\n".format(sent_elem.attrib["id"]))
            texts = list(sent_elem.xpath(".//text"))
            # Index cognates
            anns = list(sent_elem.xpath(f".//annotation"))
            anchor_ann_index = {}
            for ann in anns:
                anchor_ann_index.setdefault(ann.attrib["anchor"], []).append(ann)
            # Reorder
            for anchor, anns in anchor_ann_index.items():
                correct_order = get_ann_langs(anchor, texts, anns)
                logger.debug(f"Correct order: {correct_order}\n")
                for ann, lang in zip(anns, correct_order):
                    if ann.attrib["lang"] != lang:
                        reorderings += 1
                        logger.debug("Before\n")
                        logger.debug(etree.tostring(ann, encoding="unicode").strip())
                        ann.attrib["lang"] = lang
                        logger.debug("After\n")
                        logger.debug(etree.tostring(ann, encoding="unicode").strip())

        return proc_sent

    if order == "set":
        proc_sent = mk_proc_sent(get_correct_order_set)
    elif order == "multiset":
        proc_sent = mk_proc_sent(get_correct_order_multiset)
    elif order == "intersect-grow":
        proc_sent = mk_proc_sent(get_correct_order_text_intersect_grow)

    try:
        transform_sentences(inf, proc_sent, outf)
    finally:
        logger.info("Reorderings: {}\n".format(reorderings))


@fix_eurosense.command("retag-languages")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
@click.option("--trace-only/--fix")
def retag_languages(inf: IO, outf: IO, trace_only):
    problem_sentences = 0
    total_problems = 0
    unfixable_problems = 0

    def proc_sent(sent_elem):
        nonlocal problem_sentences
        nonlocal total_problems
        nonlocal unfixable_problems

        texts = list(sent_elem.xpath(".//text"))
        anns = list(sent_elem.xpath(f".//annotation"))

        text_langs = {}
        lang_texts = {}
        langs = []
        for text_idx, text in enumerate(texts):
            lang = text.attrib["lang"]
            langs.append(lang)
            text_langs[text_idx] = lang
            lang_texts[lang] = text_idx

        # Find problem annotations
        problem_annotation_idxs = []
        anchors = {}
        for text in texts:
            sent = text.text
            lang = text.attrib["lang"]
            cursor = 0
            for ann_idx, ann in enumerate(anns):
                if ann.attrib["lang"] != lang:
                    continue
                if sent is None:
                    match_pos = -1
                else:
                    match_pos = find_word(sent, ann.attrib["anchor"], cursor)
                if match_pos == -1:
                    problem_annotation_idxs.extend(range(ann_idx, len(anns)))
                    break
                else:
                    anchors[ann_idx] = (lang, match_pos)
                cursor = match_pos

        # Tally problems
        num_problems = len(problem_annotation_idxs)
        if num_problems:
            problem_sentences += 1
        else:
            return
        total_problems += num_problems

        # Exit if tracing only
        if trace_only:
            return

        # Try to fix the problems
        for problem_annotation_idx in problem_annotation_idxs:
            ann = anns[problem_annotation_idx]
            # Find any known correct annotations to use as anchors
            prev_anchor = None
            prev_idx = problem_annotation_idx - 1
            while prev_idx >= 0:
                if prev_idx in anchors:
                    prev_anchor = anchors[prev_idx]
                    break
                prev_idx -= 1
            if prev_anchor is None:
                prev_anchor = (langs[0], 0)
            next_anchor = None
            next_idx = problem_annotation_idx + 1
            while next_idx < len(anns):
                if next_idx in anchors:
                    next_anchor = anchors[next_idx]
                    break
                next_idx += 1
            if next_anchor is None:
                next_anchor = (langs[-1], len(texts[-1]))

            lang, cursor = prev_anchor
            anchored = False
            while not anchored:

                def next_lang():
                    nonlocal cursor
                    nonlocal lang
                    next_text_idx = lang_texts[lang] + 1
                    if next_text_idx >= len(lang_texts):
                        return True
                    cursor = 0
                    lang = text_langs[next_text_idx]

                text_idx = lang_texts[lang]
                sent = texts[text_idx].text
                if sent is None:
                    if next_lang():
                        break
                    continue
                match_pos = find_word(sent, ann.attrib["anchor"], cursor)
                if match_pos == -1:
                    if next_lang():
                        break
                    continue
                else:
                    anchors[problem_annotation_idx] = (lang, match_pos)
                    anchored = True
                    ann.attrib["lang"] = lang

            if not anchored:
                logger.debug(
                    "Could not anchor annotation #{} in sentence #{}\n".format(
                        problem_annotation_idx, sent_elem.attrib["id"]
                    )
                )
                logger.debug(etree.tostring(ann, encoding="unicode").strip())
                unfixable_problems += 1

    try:
        transform_sentences(inf, proc_sent, outf)
    finally:
        logger.info("Problem sentences: {}\n".format(problem_sentences))
        logger.info("Total problems: {}\n".format(total_problems))
        logger.info("Unfixable problems: {}\n".format(unfixable_problems))


@fix_eurosense.command("rm-empty-texts")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def rm_empty_texts(inf: IO, outf: IO):
    removed = 0

    def proc_sent(sent_elem):
        nonlocal removed
        for text in sent_elem.xpath(".//text"):
            if text.text is None:
                removed += 1
                text.getparent().remove(text)

    try:
        transform_sentences(inf, proc_sent, outf)
    finally:
        logger.info("Removed empty sentences: {}\n".format(removed))


@fix_eurosense.command("drop-unanchorable")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def drop_unanchorable(inf: IO, outf: IO):
    dropped = 0

    def proc_sent(sent_elem):
        nonlocal dropped
        for annotation in sent_elem.xpath(".//annotation"):
            anchor_text = annotation.attrib["anchor"]
            found = False
            for text in sent_elem.xpath(".//text"):
                if find_word(text.text or "", anchor_text) != -1:
                    found = True
                    break
            if not found:
                dropped += 1
                logger.info(f"Anchor not found: {anchor_text}")
                logger.info(sent_elem.attrib["id"])
                annotation.getparent().remove(annotation)

    try:
        transform_sentences(inf, proc_sent, outf)
    finally:
        logger.info("Dropped unanchorable annotations: {}\n".format(dropped))


@fix_eurosense.command("pipeline")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("outf", type=click.Path())
def pipeline(inf, outf):
    cmds = (
        python[fix_eurosense_py, "drop-unanchorable", inf, "-"]
        | python[
            fix_eurosense_py, "reorder-cognates", "--order=intersect-grow", "-", "-"
        ]
        | python[fix_eurosense_py, "retag-languages", "-", "-"]
        | python[fix_eurosense_py, "rm-empty-texts", "-", outf]
    )
    print(cmds)
    cmds(retcode=[-13, 0], stderr=sys.stderr)


if __name__ == "__main__":
    fix_eurosense()
