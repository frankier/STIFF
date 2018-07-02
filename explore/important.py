from nltk.corpus import wordnet, wordnet_ic
import click

import stiff.fix_cmn  # noqa

_semcor_ic = None


def ic(lemma):
    global _semcor_ic
    if _semcor_ic is None:
        _semcor_ic = wordnet_ic.ic("ic-semcor.dat")
    synset = lemma.synset()
    if synset.pos() not in _semcor_ic:
        return 0
    return _semcor_ic[synset.pos()][synset.offset()]


def ic_lemmas(lemma_name, lang):
    lemmas = wordnet.lemmas(lemma_name, lang=lang)
    return (sum(ic(l) for l in lemmas), lemma_name, lemmas)


def important_lemmas(lang):
    return sorted(
        (ic_lemmas(l, lang) for l in wordnet.all_lemma_names(lang=lang)), reverse=True
    )


@click.command("important")
@click.argument("lang")
@click.argument("limit", type=int, required=False)
def important(lang, limit=50):
    print(" = Important = ")
    lemmas = important_lemmas(lang)
    for x in lemmas[:limit]:
        print(x)
    print()
    print(" = Important multiwords (+) = ")
    for x in [y for y in lemmas if "+" in y[1]][:limit]:
        print(x)
    print()
    print(" = Important multiwords (_) = ")
    for x in [y for y in lemmas if "_" in y[1]][:limit]:
        print(x)
    print()
    print(" = Longest = ")
    for x in sorted(lemmas, key=lambda tpl: len(tpl[1]), reverse=True)[:limit]:
        print(x)


if __name__ == "__main__":
    important()
