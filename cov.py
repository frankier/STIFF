import click
from filter_utils import iter_sentences
import pandas as pd
from streamz import Stream
from streamz.dataframe import DataFrame


@click.command("cov")
@click.argument("inf", type=click.File("rb"))
def cov(inf):
    source = Stream()
    header = pd.DataFrame({"toks": [], "anns": [], "cov": []})
    sdf = DataFrame(source, example=header)

    def get_cov(sent):
        toks = len(sent.xpath("text")[0].text.split(" "))
        anns = len(sent.xpath("annotation"))
        source.emit(
            pd.DataFrame({"toks": [toks], "anns": [anns], "cov": [anns / toks]})
        )

    toks_sum = sdf.toks.sum().stream.gather().sink_to_list()
    anns_sum = sdf.anns.sum().stream.gather().sink_to_list()
    iter_sentences(inf, get_cov)
    print(anns_sum[-1], toks_sum[-1])


if __name__ == "__main__":
    cov()
