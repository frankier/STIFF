from nltk.corpus import wordnet
import click


@click.command("trace-wn")
@click.argument("lang")
@click.argument("corpus", type=click.File("r"))
def trace_wn(lang, corpus):
    for line in corpus:
        for word in line.split(" "):
            print(word, wordnet.lemmas(word, lang=lang))


if __name__ == "__main__":
    trace_wn()
