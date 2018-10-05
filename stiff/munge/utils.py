from lxml import etree
from typing import Callable, IO, List
from stiff.utils.xml import eq_matcher, transform_blocks


def transform_senseval_contexts(
    inf: IO, transform_tokens: Callable[[List[str]], List[str]], outf: IO
) -> None:
    def transform_context(context: etree.ElementBase) -> etree.ElementBase:
        sent: List[str] = []
        before = context.text
        head_tag = context[0]
        head = head_tag.text
        after = head_tag.tail

        before_tok = before.strip().split(" ")
        head_tok = head.split(" ")
        after_tok = after.strip().split(" ")

        sent = before_tok + head_tok + after_tok
        new_sent = transform_tokens(sent)

        new_before = new_sent[: len(before_tok)]
        new_head = new_sent[len(before_tok) : len(before_tok) + len(head_tok)]
        new_after = new_sent[len(before_tok) + len(head_tok) :]

        context.text = "\n" + "".join(tok + " " for tok in new_before)
        head_tag.text = " ".join(tok for tok in new_head)
        head_tag.tail = "".join(" " + tok for tok in new_after) + "\n"
        return context

    transform_blocks(eq_matcher("context"), inf, transform_context, outf)
