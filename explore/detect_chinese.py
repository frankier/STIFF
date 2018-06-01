import click
import mafan
from mafan import text
import opencc
import pandas as pd
import os
import csv
from collections import Counter
from pprint import pprint
from itertools import takewhile, repeat
import pickle

TRACE = False

MAFAN_NAMES = {
    mafan.TRADITIONAL: "traditional",
    mafan.SIMPLIFIED: "simplified",
    mafan.EITHER: "either",
    mafan.BOTH: "both",
    mafan.NEITHER: "neither",
}

opencc_s2t = opencc.OpenCC("s2t.json")
opencc_t2s = opencc.OpenCC("t2s.json")
if os.path.exists("yue/svm.pkl"):
    detect_yue_clf = pickle.load(open("yue/svm.pkl", "rb"))


@click.group()
def cli():
    pass


def opencc_detect(text):
    s2t = opencc_s2t.convert(text)
    t2s = opencc_t2s.convert(text)
    if text == s2t and text == t2s:
        return "either"
    elif text == s2t:
        return "traditional"
    elif text == t2s:
        return "simplified"
    else:
        return "both/neither"


def is_chinese_filename(filename):
    return filename.split(".")[-1] not in ["fi", "ids"]


def proc_line(line, get_yue=False):
    from yue import feat

    line = line.strip()
    mefan_id = text.identify(line)
    opencc = opencc_detect(line)
    chars = len(line)
    tokens = len(line.split())
    if TRACE:
        print(line)
        print("Mefan says", MAFAN_NAMES[mefan_id])
        print("OpenCC says", opencc)
        print("Chars", chars)
        print("Tokens", tokens)
    res = [mefan_id, opencc]
    if get_yue:
        yue = detect_yue_clf.predict([feat(line)])[0]
        res += [yue]
    return res + [chars, tokens]


class CsvOut:
    def __init__(self, fp):
        self.w = csv.writer(fp)

    def head(self, h):
        self.w.writerow(h)

    def row(self, r):
        self.w.writerow(r)


class MeanOut:
    def __init__(self, groupby=(), categorical=()):
        self.rows = 0
        self.groupby = groupby
        self.categorical = categorical
        self.groups = {}

    def head(self, h):
        self.header = h

    def row(self, r):
        for group_level in range(0, len(self.groupby) + 1):
            group = []
            for col in self.groupby[:group_level]:
                group.append(r[self.header.index(col)])
            group_tuple = tuple(group)
            if group_tuple not in self.groups:
                counters = {}
                self.groups[group_tuple] = counters
            else:
                counters = self.groups[group_tuple]
            for idx, (h, v) in enumerate(zip(self.header, r)):
                if h in self.categorical:
                    if h not in counters:
                        counter = Counter()
                        counters[h] = counter
                    else:
                        counter = counters[h]
                    counter[v] += 1
                else:
                    if h not in counters:
                        sum_count = [0, 0]
                        counters[h] = sum_count
                    else:
                        sum_count = counters[h]
                    sum_count[0] += v
                    sum_count[1] += 1

    @property
    def means(self):
        mean_groups = {}
        for group_tuple, counters in self.groups.items():
            mean_counters = {}
            for header, counter in counters.items():
                if header in self.categorical:
                    total = sum(counter.values())
                    mean_counters[header] = {k: v / total for k, v in counter.items()}
                else:
                    mean_counters[header] = counter[0] / counter[1]
            mean_groups[group_tuple] = mean_counters
        return mean_groups


def lines(fp):
    fp.seek(0)
    bufgen = takewhile(
        lambda x: x, (fp.buffer.raw.read(1024 * 1024) for _ in repeat(None))
    )
    res = sum(buf.count(b"\n") for buf in bufgen)
    fp.seek(0)
    return res


def analyse_corpus(corpus, out, ids=None, show_progress=False):
    if ids:
        cols = ["id"]
    else:
        cols = []
    cols += ["mefan", "opencc", "chars", "tokens", "chars/tokens"]
    out.head(cols)
    lc = lines(corpus)
    if ids:
        it = zip(corpus, ids)

        def proc_it(elem):
            out.row([elem[1].split()[0]] + proc_line(elem[0]))

    else:
        it = corpus

        def proc_it(line):
            out.row(proc_line(line))

    if show_progress:
        with click.progressbar(it, length=lc) as pit:
            for e in pit:
                proc_it(e)
    else:
        for e in it:
            proc_it(e)


@cli.command("multiple")
@click.argument("corpus")
def multiple(corpus):
    for root, dirs, files in os.walk(corpus):
        if not any(is_chinese_filename(fn) for fn in files):
            continue
        for fn in files:
            if not is_chinese_filename(fn):
                continue


@cli.command("single")
@click.argument("corpus", type=click.File("r"))
@click.argument("ids", type=click.File("r"), required=False)
@click.option("--df-out", default=None)
def single(corpus, ids, df_out):
    if df_out:
        analyse_corpus(corpus, CsvOut(df_out), ids, show_progress=True)
    else:
        if ids:
            mean_out = MeanOut(("id",), ("id", "mefan", "opencc"))
        else:
            mean_out = MeanOut(categorical=("id", "mefan", "opencc"))
        analyse_corpus(corpus, mean_out, ids, show_progress=True)
        pprint(mean_out.means)


@cli.command("yue")
@click.argument("corpus", type=click.File("r"))
@click.argument("ids", type=click.File("r"))
def yue(corpus, ids):
    mean_out = MeanOut(("id",), ("id", "mefan", "opencc", "yue"))
    analyse_corpus(corpus, mean_out, ids, show_progress=True)
    for group, counts in mean_out.means.items():
        if counts["yue"].get("yue", 0.0) > 0.1:
            print(group)
            print(counts)


@cli.command("analyse")
@click.argument("csv", type=click.File("r"))
def analyse(csv):
    df = pd.DataFrame.from_csv(csv)
    print("Sentences")
    print(len(df))
    print("Mefan counts")
    mefan_counts = df["mefan"].value_counts() / len(df)
    mefan_counts.index = mefan_counts.index.map(MAFAN_NAMES)
    print(mefan_counts)
    print("OpenCC counts")
    opencc_counts = df["opencc"].value_counts() / len(df)
    print(opencc_counts)
    print("Tokens")
    print(df["tokens"].mean())
    print("Chars/token")
    print((df["chars"] / df["tokens"]).mean())


def get_movie_ids(fp):
    movie_ids = set()
    for line in fp:
        movie_ids.add(line.split()[0])
    return movie_ids


@cli.command("intersect")
@click.argument("ids1", type=click.File("r"))
@click.argument("ids2", type=click.File("r"))
def intersect_ids(ids1, ids2):
    movies1 = get_movie_ids(ids1)
    movies2 = get_movie_ids(ids2)
    print("movies1", len(movies1))
    print("movies2", len(movies2))
    print("movies1 - movies2", len(movies1 - movies2))
    print("movies2 - movies2", len(movies2 - movies1))
    print("movies1 & movies2", len(movies1 & movies2))
    print("movies1 | movies2", len(movies1 | movies2))


def mk_mean_out():
    return MeanOut(("id",), ("id", "mefan", "opencc"))


def get_means(corpus, ids):
    mean_out = mk_mean_out()
    analyse_corpus(corpus, mean_out, ids, show_progress=True)
    means = mean_out.means
    del means[()]
    return means


@cli.command("confsmat-analyse")
@click.argument("cn_corpus", type=click.File("r"))
@click.argument("cn_ids", type=click.File("r"))
@click.argument("tw_corpus", type=click.File("r"))
@click.argument("tw_ids", type=click.File("r"))
@click.argument("out", type=click.File("wb"))
def confsmat_analyse(cn_corpus, cn_ids, tw_corpus, tw_ids, out):
    cn_means = get_means(cn_corpus, cn_ids)
    tw_means = get_means(tw_corpus, tw_ids)

    pickle.dump((cn_means, tw_means), out)


@cli.command("confsmat-cls")
@click.argument("means_pickle", type=click.File("rb"))
@click.argument("out", type=click.File("wb"))
def confsmat_cls(means_pickle, out):
    from itertools import chain

    cn_means, tw_means = pickle.load(means_pickle)

    print("Got means")

    pred_labels = ["zh_CN"] * len(cn_means) + ["zh_TW"] * len(tw_means)
    actual_labels = []
    for group, means in chain(cn_means.items(), tw_means.items()):
        trad = means["opencc"].get("traditional", 0.0)
        simp = means["opencc"].get("simplified", 0.0)
        eith = means["opencc"].get("either", 0.0)
        neit = means["opencc"].get("both/neither", 0.0)
        trad_sup = trad + eith
        simp_sup = simp + eith
        trad_opp = simp + neit
        simp_opp = trad + neit
        if trad_sup > 0.66:
            actual_labels.append("trad")
        elif simp_sup > 0.66:
            actual_labels.append("simp")
        else:
            print(group)
            print("trad", trad_sup, trad_opp)
            print("simp", simp_sup, simp_opp)
            actual_labels.append("neit")
    result = {"pred": pred_labels, "act": actual_labels}
    pickle.dump(result, out)


@cli.command("get-film")
@click.argument("needle")
@click.argument("corpus", type=click.File("r"))
@click.argument("ids", type=click.File("r"))
def get_film(needle, corpus, ids):
    for line, id in zip(corpus, ids):
        if id.split()[0] == needle:
            print(line, end="")


if __name__ == "__main__":
    cli()
