import click
from stiff.filter_utils import iter_sentences
import pandas as pd
from streamz import Stream
from streamz.dataframe import DataFrame


@click.command("cov")
@click.argument("inf", type=click.File("rb"))
@click.argument("subtotal", type=int, required=False)
def cov(inf, subtotal=None):
    """
    Produce a report of how much of a corpus in Eurosense/STIFF format is
    covered by annotations.
    """
    source = Stream()
    header = pd.DataFrame({"toks": [], "anns": [], "cov": []})
    sdf = DataFrame(source, example=header)

    toks_sum = sdf.toks.sum().stream.gather().sink_to_list()
    anns_sum = sdf.anns.sum().stream.gather().sink_to_list()

    def print_cov():
        sents = len(anns_sum)
        print("Coverage at {} sentences:".format(sents))
        print(anns_sum[-1], toks_sum[-1], anns_sum[-1] / toks_sum[-1])

    try:
        for idx, sent in enumerate(iter_sentences(inf)):
            toks = len(sent.xpath("text")[0].text.split(" "))
            anns = len(sent.xpath("annotations/annotation"))
            source.emit(
                pd.DataFrame({"toks": [toks], "anns": [anns], "cov": [anns / toks]})
            )
            idx1 = idx + 1
            if subtotal is not None and idx1 % subtotal == 0:
                print_cov()
    finally:
        if len(anns_sum):
            print_cov()


if __name__ == "__main__":
    cov()
