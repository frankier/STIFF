from lxml import etree
import click
from stiff.utils.anns import get_ann_pos, get_ann_pos_dict
from stiff.utils.xml import iter_sentences, iter_sent_to_pairs, iter_sentence_id_pairs
import pandas as pd
from streamz import Stream
from streamz.dataframe import DataFrame
from os import listdir
from os.path import join as pjoin


@click.group("eval")
def eval():
    """
    (Intrinsic) evaluation of sense annotated corpus quality.
    """
    pass


class SampleGoldIterationException(Exception):
    pass


def align_with_gold(gold_sents, guess_sents, max_slack=1000):
    while 1:
        try:
            gold_id, gold_sent = next(gold_sents)
        except StopIteration:
            return
        skipped = 0
        while 1:
            try:
                guess_id, guess_sent = next(guess_sents)
            except StopIteration:
                raise SampleGoldIterationException(
                    "GUESS ended before all GOLD sentences were found "
                    + f"trying to find {gold_id}"
                )
            if guess_id == gold_id:
                break
            skipped += 1
            if skipped > max_slack:
                raise SampleGoldIterationException(
                    f"Skipped more than {max_slack} sentences in GUESS "
                    + f"trying to find {gold_id}"
                )
        yield gold_id, gold_sent, guess_sent


def anns_to_set(anns):
    return {(int(get_ann_pos_dict(ann)["token"]), ann.text) for ann in anns}


def get_cov_map(toks, anns):
    cov_map = [set() for _ in range(toks)]
    for ann in anns:
        tok, tok_len = get_ann_pos(ann)
        for idx in range(tok, tok + tok_len):
            cov_map[idx].add(ann.text)
    return cov_map


def score_anns_tokwise(gold_anns, guess_anns, toks):
    gold_cov = get_cov_map(toks, gold_anns)
    guess_cov = get_cov_map(toks, guess_anns)
    tp = 0
    fp = 0
    fn = 0
    for gold, guess in zip(gold_cov, guess_cov):
        if gold & guess:
            tp += 1
        elif gold:
            fn += 1
        incorrect = guess - gold
        if incorrect:
            fp += len(incorrect)
    return tp, fp, fn


def score_anns_annwise(gold_anns, guess_anns, _toks):
    gold_ann_set = anns_to_set(gold_anns)
    guess_ann_set = anns_to_set(guess_anns)
    tp = len(gold_ann_set & guess_ann_set)
    fp = len(guess_ann_set - gold_ann_set)
    fn = len(gold_ann_set - guess_ann_set)
    return tp, fp, fn


def calc_pr(tp, fp, fn):
    if tp == 0:
        return 0, 0, 0
    p = tp / (tp + fp)
    r = tp / (tp + fn)
    return (p, r, 2 * p * r / (p + r))


def get_num_tokens(gold_sent, guess_sent):
    gold_texts = gold_sent.xpath(".//text")
    assert len(gold_texts) == 1
    guess_texts = guess_sent.xpath(".//text")
    assert len(guess_texts) == 1
    sent_text = gold_texts[0].text
    assert sent_text == guess_texts[0].text
    return sent_text.count(" ") + 1 if sent_text else 0


def pr_one(gold_etree, guess_fp, score_func, trace_individual=False):
    total_tp = 0
    total_fp = 0
    total_fn = 0
    gold_sents = list(iter_sent_to_pairs(iter(gold_etree.xpath("//sentence"))))
    guess_sents = iter_sentence_id_pairs(guess_fp)
    for idx, (sent_id, gold_sent, guess_sent) in enumerate(
        align_with_gold(iter(gold_sents), guess_sents)
    ):

        gold_anns = gold_sent.xpath(".//annotation")
        guess_anns = guess_sent.xpath(".//annotation")
        num_tokens = get_num_tokens(gold_sent, guess_sent)
        tp, fp, fn = score_func(gold_anns, guess_anns, num_tokens)
        if trace_individual:
            print("#{:02d} {}".format(idx, sent_id))
            print(
                "P: {}, R: {}, F_1: {}, tp: {}, fp: {}, fn: {}".format(
                    *calc_pr(tp, fp, fn), tp, fp, fn
                )
            )
        total_tp += tp
        total_fp += fp
        total_fn += fn
    return calc_pr(total_tp, total_fp, total_fn)


def get_score_func(score):
    if score == "ann":
        return score_anns_annwise
    else:
        assert score == "tok"
        return score_anns_tokwise


@eval.command("pr")
@click.argument("gold", type=click.File("rb"), nargs=1)
@click.argument("guess", type=click.File("rb"), nargs=-1)
@click.option("--trace-individual/--no-trace-individual", default=False)
@click.option("--score", type=click.Choice(["ann", "tok"]))
def pr(gold, guess, trace_individual, score):
    score_func = get_score_func(score)
    gold_etree = etree.parse(gold)
    for guess_fp in guess:
        print(guess_fp)
        print(pr_one(gold_etree, guess_fp, score_func, trace_individual))


@eval.command("pr-eval")
@click.argument("gold", type=click.File("rb"))
@click.argument("eval", type=click.Path())
@click.argument("csv_out", type=click.Path())
@click.option("--trace-individual/--no-trace-individual", default=False)
@click.option("--score", type=click.Choice(["ann", "tok"]))
def pr_eval(gold, eval, csv_out, trace_individual, score):
    score_func = get_score_func(score)
    gold_etree = etree.parse(gold)
    data = []
    for entry in listdir(eval):
        name = entry.rsplit(".", 1)[0]
        if trace_individual:
            print(name)
        precision, recall, f_1 = pr_one(
            gold_etree, open(pjoin(eval, entry), "rb"), score_func, trace_individual
        )
        data.append(
            {"name": name, "precision": precision, "recall": recall, "f_1": f_1}
        )
    df = pd.DataFrame(data)
    print(df)
    df.to_csv(csv_out)


INCH_PTS = 72


@eval.command("pr-plot")
@click.argument("opensubs18_csv", type=click.Path())
@click.argument("eurosense_csv", type=click.Path(), required=False)
@click.option("--out")
def pr_plot(opensubs18_csv, eurosense_csv=None, out=None):
    import matplotlib.pyplot as plt
    from adjustText import adjust_text
    import pareto
    from brokenaxes import brokenaxes
    import matplotlib as mpl

    mpl.rcParams.update(
        {"font.family": "serif", "font.serif": [], "font.sans-serif": []}
    )

    opensubs18_df = pd.read_csv(opensubs18_csv)

    nondominated = pareto.eps_sort(
        opensubs18_df[["precision", "recall"]],
        [0, 1],
        maximize_all=True,
        attribution=True,
    )
    nondominated_idxs = [nd[-1] for nd in nondominated]

    opensubs18_df["type"] = pd.Series(
        [
            "stiff-nondom" if idx in nondominated_idxs else "stiff"
            for idx in opensubs18_df.index
        ]
    )

    type_markers = {"stiff": ("o", "k"), "stiff-nondom": ("D", "b")}

    if eurosense_csv is not None:
        type_markers["eurosense"] = ("s", "y")
        eurosense_df = pd.read_csv(eurosense_csv)
        eurosense_df["type"] = "eurosense"
        eurosense_df["name"] = eurosense_df["name"].str.replace("high", "eurosense")
        df = pd.concat([opensubs18_df, eurosense_df], ignore_index=True)
    else:
        df = opensubs18_df

    print(df)

    fig = plt.gcf()
    fig.set_size_inches(645.0 / INCH_PTS, 441.0 / INCH_PTS)

    bax = brokenaxes(
        xlims=((0, 0.01), (0.29, 1)),
        ylims=((0, 0.51), (0.99, 1)),
        hspace=0.05,
        wspace=0.05,
    )

    for type, (marker, c) in type_markers.items():
        group_df = df[df.type == type]
        bax.scatter(
            x=group_df["precision"], y=group_df["recall"], marker=marker, c=c, s=10
        )
    texts = []
    for idx, row in df.iterrows():
        texts.append(
            bax.axs[3].text(
                row["precision"], row["recall"], row["name"], ha="center", va="center"
            )
        )
    adjust_text(texts)
    bax.set_xlabel("Precision")
    bax.set_ylabel("Recall")
    if out is not None:
        plt.savefig(out, bbox_inches="tight")
    else:
        plt.show()


@eval.command("cov")
@click.argument("inf", type=click.File("rb"))
@click.argument("subtotal", type=int, required=False)
def cov(inf, subtotal=None):
    """
    Produce a report of how much of a corpus in Eurosense/STIFF format is
    covered by annotations.
    """
    source = Stream()
    header = pd.DataFrame(
        {"toks": [], "anns": [], "unambg_anns": [], "uniq_anns": [], "cover": []}
    )
    sdf = DataFrame(source, example=header)
    sums = {}
    for col in ["toks", "anns", "unambg_anns", "uniq_anns", "cover"]:
        sums[col] = getattr(sdf, col).sum().stream.gather().sink_to_list()

    ambg_source = Stream()
    ambg_header = pd.DataFrame({"ambg": []})
    ambg_sdf = DataFrame(ambg_source, example=ambg_header)
    ambg_hist = ambg_sdf.ambg.value_counts().stream.gather().sink_to_list()

    def print_cov():
        sents = len(sums["anns"])
        print("Coverage at {} sentences:".format(sents))
        print(
            "Total annotations, unique annotations, unambiguous annotations, "
            "tokens, tokens covered, proportion of tokens covered"
        )
        print(
            sums["anns"][-1],
            sums["uniq_anns"][-1],
            sums["unambg_anns"][-1],
            sums["toks"][-1],
            sums["cover"][-1],
            sums["cover"][-1] / sums["toks"][-1],
        )
        print(ambg_hist[-1])

    try:
        # XXX: take into account token length for coverage
        for idx, sent in enumerate(iter_sentences(inf)):
            toks = len(sent.xpath("text")[0].text.split(" "))
            anns = sent.xpath("annotations/annotation")
            num_anns = len(anns)
            ann_index = {}
            cov_map = [0] * toks
            for ann in anns:
                tok, tok_len = get_ann_pos(ann)
                ann_index.setdefault(tok, []).append(ann)
                for idx in range(tok, tok + tok_len):
                    cov_map[idx] += 1
            unambg_anns = 0
            uniq_anns = 0
            for ann_list in ann_index.values():
                ambg = len(ann_list)
                ambg_source.emit(pd.DataFrame({"ambg": [ambg]}))
                if ambg == 1:
                    unambg_anns += 1
                uniq_anns += 1
            source.emit(
                pd.DataFrame(
                    {
                        "toks": [toks],
                        "anns": [num_anns],
                        "unambg_anns": [unambg_anns],
                        "uniq_anns": [uniq_anns],
                        "cover": [toks - cov_map.count(0)],
                    }
                )
            )
            idx1 = idx + 1
            if subtotal is not None and idx1 % subtotal == 0:
                print_cov()
    finally:
        if len(sums["anns"]):
            print_cov()


@eval.command("ambg")
@click.argument("inf", type=click.File("rb"))
def ambg(inf):
    pass


if __name__ == "__main__":
    eval()
