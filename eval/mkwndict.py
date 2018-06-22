import click

from finntk.wordnet.reader import fiwn_encnt
from finntk.wordnet.utils import fi2en_post


@click.command()
@click.option("--en-synset-ids/--fi-synset-ids")
def main(en_synset_ids):
    lemma_names = fiwn_encnt.all_lemma_names()

    for lemma_name in lemma_names:
        lemmas = fiwn_encnt.lemmas(lemma_name)
        synsets = []
        for lemma in lemmas:
            synset = lemma.synset()
            post_synset_id = fiwn_encnt.ss2of(synset)
            if en_synset_ids:
                post_synset_id = fi2en_post(post_synset_id)
            synsets.append("{}:{}".format(post_synset_id, lemma.count()))
        print("{}\t{}".format(lemma_name, " ".join(synsets)))


if __name__ == "__main__":
    main()
