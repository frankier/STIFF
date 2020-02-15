from stiff.munge.utils import space_tokenize
from stiff.utils.xml import free_elem, iter_blocks


def iter_lexelts(inf, synsets=False):
    for lexelt in iter_blocks("lexelt")(inf):
        if synsets:
            yield lexelt, lexelt.get("synset")
        else:
            item = lexelt.get("item")
            pos = lexelt.get("pos")
            yield lexelt, (item, pos)


def proc_instance(instance):
    contexts = instance.xpath("context")
    assert len(contexts) == 1
    context_tag = contexts[0]
    heads = context_tag.xpath("head")
    assert len(heads) == 1
    head_tag = heads[0]
    head_text = head_tag.text
    before_texts = head_tag.xpath("preceding-sibling::text()")
    assert len(before_texts) == 1
    before_text = before_texts[0]
    after_texts = head_tag.xpath("following-sibling::text()")
    assert len(after_texts) == 1
    after_text = after_texts[0]
    inst_id = instance.attrib["id"]
    free_elem(instance)
    return (
        inst_id,
        (
            space_tokenize(before_text),
            space_tokenize(head_text),
            space_tokenize(after_text),
        ),
    )


def iter_instances(inf, synsets=False):
    for lexelt, item_pos in iter_lexelts(inf, synsets=synsets):
        for instance in lexelt.xpath("instance"):
            inst_id, texts = proc_instance(instance)
            yield inst_id, item_pos, texts


def iter_instances_grouped(inf, synsets=False):
    for lexelt, item_pos in iter_lexelts(inf, synsets=synsets):

        def group_iter():
            for instance in lexelt.xpath("instance"):
                yield proc_instance(instance)

        yield item_pos, int(lexelt.xpath("count(instance)")), group_iter()


def split_tagged_token(token):
    wf, rest = token.split("|LEM|")
    lem, pos = rest.split("|POS|")
    return wf, lem, pos


def split_tagged_tokens(tokens):
    return map(split_tagged_token, tokens)


def norm_wf_lemma_of_tokens(tokens):
    return [(wf.lower(), lem) for wf, lem, _ in split_tagged_tokens(tokens)]


def next_key(keyin):
    bits = next(keyin).strip().split()
    return bits[0], bits[1:]


def iter_keys(keyin):
    while 1:
        try:
            yield next_key(keyin)
        except StopIteration:
            return
