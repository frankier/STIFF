import sys
from lxml import etree
from typing import IO
import click
from stiff.utils.xml import transform_sentences, iter_sentences
import os
from os.path import join as pjoin
from plumbum import local

python = local[sys.executable]

dir = os.path.dirname(os.path.realpath(__file__))
fix_eurosense_py = pjoin(dir, "fix-eurosense.py")

# This file is a WIP


@click.group("fix-eurosense")
def fix_eurosense():
    """
    Commands to fix up problems in Eurosense
    """
    pass


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
                match_pos = text.text.find(anchor)
            if match_pos == -1:
                alternatives = []
                for lang, text in lang_texts.items():
                    if text.text is None:
                        continue
                    match_pos = text.text.find(anchor)
                    if match_pos != -1:
                        alternatives.append(lang)
                print(
                    "Sent #{}: '{}' not found in {}, could be {}".format(
                        sent_elem.attrib["id"], anchor, lang, " ".join(alternatives)
                    )
                )


@fix_eurosense.command("reorder-cognates")
@click.argument("inf", type=click.File("rb"))
@click.argument("outf", type=click.File("wb"))
def reorder_cognates(inf: IO, outf: IO):
    reorderings = 0

    def proc_sent(sent_elem):
        nonlocal reorderings
        sys.stderr.write("Sentence #{}\n".format(sent_elem.attrib["id"]))
        # Get lang order
        texts = list(sent_elem.xpath(".//text"))
        langs = []
        for text_idx, text in enumerate(texts):
            lang = text.attrib["lang"]
            langs.append(lang)
        # Index cognates
        anns = list(sent_elem.xpath(f".//annotation"))
        anchor_ann_index = {}
        for ann in anns:
            anchor_ann_index.setdefault(ann.attrib["anchor"], []).append(ann)
        # Reorder
        for anchor, anns in anchor_ann_index.items():
            ann_langs = set()
            for ann in anns:
                ann_langs.add(ann.attrib["lang"])
            correct_order = []
            for lang in langs:
                if lang in ann_langs:
                    correct_order.append(lang)
            for ann, lang in zip(anns, correct_order):
                if ann.attrib["lang"] != lang:
                    reorderings += 1
                    sys.stderr.write("Before\n")
                    sys.stderr.write(etree.tostring(ann, encoding="unicode"))
                    ann.attrib["lang"] = lang
                    sys.stderr.write("After\n")
                    sys.stderr.write(etree.tostring(ann, encoding="unicode"))

    try:
        transform_sentences(inf, proc_sent, outf)
    finally:
        sys.stderr.write("Reorderings: {}\n".format(reorderings))


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
        for text_idx, text in enumerate(texts):
            sent = text.text
            if sent is None:
                continue
            lang = text.attrib["lang"]
            cursor = 0
            for ann_idx, ann in enumerate(anns):
                if ann.attrib["lang"] != lang:
                    continue
                ann = anns[ann_idx]
                match_pos = sent.find(ann.attrib["anchor"], cursor)
                if match_pos == -1:
                    problem_annotation_idxs.extend(range(ann_idx, len(anns)))
                    break
                else:
                    anchors[ann_idx] = (lang, match_pos)
                cursor = match_pos
            text_idx += 1

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
                match_pos = sent.find(ann.attrib["anchor"], cursor)
                if match_pos == -1:
                    if next_lang():
                        break
                    continue
                else:
                    anchors[problem_annotation_idx] = (lang, match_pos)
                    anchored = True
                    ann.attrib["lang"] = lang

            if not anchored:
                sys.stderr.write(
                    "Could not anchor annotation #{} in sentence #{}\n".format(
                        problem_annotation_idx, sent_elem.attrib["id"]
                    )
                )
                sys.stderr.write(etree.tostring(ann, encoding="unicode"))
                unfixable_problems += 1

    try:
        transform_sentences(inf, proc_sent, outf)
    finally:
        sys.stderr.write("Problem sentences: {}\n".format(problem_sentences))
        sys.stderr.write("Total problems: {}\n".format(total_problems))
        sys.stderr.write("Unfixable problems: {}\n".format(unfixable_problems))


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
        sys.stderr.write("Removed empty sentences: {}\n".format(removed))


@fix_eurosense.command("pipeline")
@click.argument("inf", type=click.Path(exists=True))
@click.argument("outf", type=click.Path())
def pipeline(inf, outf):
    cmds = (
        python[fix_eurosense_py, "reorder-cognates", inf, "-"]
        | python[fix_eurosense_py, "retag-languages", "-", "-"]
        | python[fix_eurosense_py, "rm-empty-texts", "-", outf]
    )
    print(cmds)
    cmds(retcode=[-13, 0], stderr=sys.stderr)


if __name__ == "__main__":
    fix_eurosense()
