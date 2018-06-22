import click
from stiff.filter_utils import iter_sentences
import pandas as pd
from streamz import Stream
from streamz.dataframe import DataFrame


@click.command("cov")
@click.argument("inf", type=click.File("rb"))
def cov(inf):
    source = Stream()
    header = pd.DataFrame({"toks": [], "anns": [], "cov": []})
    sdf = DataFrame(source, example=header)

    toks_sum = sdf.toks.sum().stream.gather().sink_to_list()
    anns_sum = sdf.anns.sum().stream.gather().sink_to_list()

    for sent in iter_sentences(inf):
        toks = len(sent.xpath("text")[0].text.split(" "))
        anns = len(sent.xpath("annotation"))
        source.emit(
            pd.DataFrame({"toks": [toks], "anns": [anns], "cov": [anns / toks]})
        )
    print(anns_sum[-1], toks_sum[-1])


if __name__ == "__main__":
    cov()
