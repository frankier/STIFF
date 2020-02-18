import numpy
from lxml import etree
import click
from stiff.utils.anns import get_ann_pos, get_ann_pos_dict
from stiff.utils.xml import iter_sentences, iter_sent_to_pairs, iter_sentence_id_pairs
from stiff.data.constants import UNI_POS_WN_MAP, WN_UNI_POS_MAP
from stiff.sup_corpus import next_key, iter_lexelts
import pandas as pd
from os import listdir
from os.path import join as pjoin
from collections import Counter
from math import log2
from finntk.wordnet.reader import fiwn, fiwn_encnt
from nltk.corpus import wordnet
from matplotlib import pylab as pl
from matplotlib.ticker import MultipleLocator
from glob import glob
import seaborn as sns


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

    df = df.drop(df[df.name == "N"].index)

    print(df)

    fig = plt.gcf()
    fig.set_size_inches(645.0 / INCH_PTS, 441.0 / INCH_PTS)

    bax = brokenaxes(
        xlims=((0, 0.01), (0.24, 0.51), (0.69, 0.81), (0.99, 1)),
        ylims=((0, 0.21), (0.39, 0.43), (0.99, 1)),
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
        if row["precision"] > 0.6:
            axnum = 10
        elif row["recall"] > 0.3:
            axnum = 5
        else:
            axnum = 9
        texts.append(
            bax.axs[axnum].text(
                row["precision"], row["recall"], row["name"], ha="center", va="center"
            )
        )
    x = numpy.linspace(0, 0.6, 100)
    for eurosense in ("EC", "EP"):
        row = df[df.name == eurosense]
        p = row.precision.item()
        r = row.recall.item()
        assert p > r
        bax.plot(x, x * r / p, zorder=-1, color="#ffdddd")
    from adjustText import adjust_text

    adjust_text(texts)
    bax.set_xlabel("Precision", labelpad=0)
    bax.set_ylabel("Recall", labelpad=40)
    if out is not None:
        plt.savefig(out, bbox_inches="tight")
    else:
        plt.show()


def sent_report(inf, report_cb, subtotal=None):
    sents = 0
    done = False
    try:
        # XXX: take into account token length for coverage
        for sent in iter_sentences(inf):
            yield sent
            sents += 1
            if subtotal is not None and sents % subtotal == 0:
                print(f"Report at {sents} sentences:")
                report_cb()
        done = True
    finally:
        if sents:
            if not done:
                print(f"Terminated early after {sents} sentences.")
            else:
                print(f"Finished after {sents} sentences.")
            report_cb()


@eval.command("intrinsic")
@click.argument("inf", type=click.File("rb"))
@click.argument("subtotal", type=int, required=False)
def intrinsic(inf, subtotal=None):
    """
    Produce a report of how much of a corpus in Eurosense/STIFF format is
    covered by annotations.
    """
    sums = Counter()
    ambg_hist = Counter()

    def print_cov():
        print(
            "Total annotations, unique annotations, unambiguous annotations, "
            "tokens, tokens covered, proportion of tokens covered"
        )
        print(
            sums["anns"],
            sums["uniq_anns"],
            sums["unambg_anns"],
            sums["toks"],
            sums["cover"],
            sums["cover"] / sums["toks"],
        )
        print(ambg_hist)

    for sent in sent_report(inf, print_cov, subtotal):
        # XXX: take into account token length for coverage
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
        print("ann_index", ann_index)
        for ann_list in ann_index.values():
            ambg = len(ann_list)
            ambg_hist[ambg] += 1
            if ambg == 1:
                unambg_anns += 1
            uniq_anns += 1
        sums["toks"] += toks
        sums["anns"] += num_anns
        sums["unambg_anns"] += unambg_anns
        sums["uniq_anns"] += uniq_anns
        sums["cover"] += toks - cov_map.count(0)


def entropy(dist, total_occurs):
    lemma_entropy = 0
    for sense, occurs in dist.items():
        p = occurs / total_occurs
        if p > 0:
            lemma_entropy -= p * log2(p)
    return lemma_entropy


class EntropyCalc:
    def __init__(self):
        self.sum_entropy = 0
        self.sum_ambg = 0
        self.weight_entropy = 0
        self.weight_ambg = 0
        self.num_insts = 0
        self.num_lemmas = 0

    def add_dist(self, dist):
        insts = sum(dist.values())
        h = entropy(dist, insts)
        self.sum_entropy += h
        self.weight_entropy += insts * h
        self.sum_ambg += len(dist)
        self.weight_ambg += insts * len(dist)
        self.num_lemmas += 1
        self.num_insts += insts

    def report(self):
        print(
            "H",
            self.sum_entropy / self.num_lemmas,
            "Ambg",
            self.sum_ambg / self.num_lemmas,
        )
        print(
            "wH",
            self.weight_entropy / self.num_insts,
            "wAmbg",
            self.weight_ambg / self.num_insts,
        )


def add_senses(dist, senses):
    for sense in senses:
        dist[sense] += 1 / len(senses)


def build_uni_sense_dist(sents, keyin, vocab):
    for sent in sents:
        instances = sent.xpath("instance")
        for inst in instances:
            inst_id, senses = next_key(keyin)
            assert inst_id == inst.attrib["id"].encode()
            add_senses(vocab.setdefault(inst.attrib["lemma"], Counter()), senses)


def iter_dists_sup(inf, keyin):
    for lexelt, lemma_pos in iter_lexelts(inf):
        dist = Counter()
        for inst in lexelt.xpath("instance"):
            inst_id, senses = next_key(keyin)
            assert inst_id == inst.attrib["id"].encode()
            add_senses(dist, senses)
        yield dist


@eval.command("entropy-uni")
@click.argument("inf", type=click.File("rb"))
@click.argument("keyin", type=click.File("rb"))
@click.argument("subtotal", type=int, required=False)
def entropy_uni(inf, keyin, subtotal=None):
    """
    Works on .xml files structured around <sentence>
    """
    vocab = {}

    def print_entropy():
        calc = EntropyCalc()
        for lemma, dist in vocab.items():
            calc.add_dist(dist)
        calc.report()

    build_uni_sense_dist(sent_report(inf, print_entropy, subtotal), keyin, vocab)


@eval.command("entropy-sup")
@click.argument("inf", type=click.File("rb"))
@click.argument("keyin", type=click.File("rb"))
def entropy_sup(inf, keyin):
    """
    Works on .sup.xml files structured around <lexelt>
    """
    calc = EntropyCalc()
    for dist in iter_dists_sup(inf, keyin):
        calc.add_dist(dist)
        calc.report()


class LexAmbgCalc:
    def __init__(self, wn):
        self.wn = wn
        self.sum_ambg = 0
        self.weight_ambg = 0
        self.num_lemmas = 0
        self.num_insts = 0

    def add_lemma(self, lemma_pos, cnt):
        ambg = len(self.wn.lemmas(*lemma_pos))
        assert ambg > 0
        self.sum_ambg += ambg
        self.weight_ambg += ambg * cnt
        self.num_lemmas += 1
        self.num_insts += cnt

    def report(self):
        print(
            "lA",
            self.sum_ambg / self.num_lemmas,
            "wlA",
            self.weight_ambg / self.num_insts,
        )


def print_ambg(lemma_pos_counts, wn):
    calc = LexAmbgCalc(wn)
    for lemma_pos, cnt in lemma_pos_counts.items():
        calc.add_lemma(lemma_pos, cnt)
    calc.report()


def get_wn(lang):
    if lang == "eng":
        return wordnet
    else:
        return fiwn


@eval.command("lex-ambg-uni")
@click.argument("inf", type=click.File("rb"))
@click.argument("lang", type=click.Choice(("eng", "fin")))
@click.argument("subtotal", type=int, required=False)
def lex_ambg_uni(inf, lang, subtotal=None):
    """
    Works on .xml files structured around <sentence>
    """
    lemma_counts = Counter()

    for sent in sent_report(
        inf, lambda: print_ambg(lemma_counts, get_wn(lang)), subtotal
    ):
        instances = sent.xpath("instance")
        for inst in instances:
            lemma_counts[
                (inst.attrib["lemma"], UNI_POS_WN_MAP[inst.attrib["pos"]])
            ] += 1


@eval.command("lex-ambg-sup")
@click.argument("inf", type=click.File("rb"))
@click.argument("lang", type=click.Choice(("eng", "fin")))
def lex_ambg_sup(inf, lang):
    """
    Works on .sup.xml files structured around <lexelt>
    """
    calc = LexAmbgCalc(get_wn(lang))
    for lexelt, lemma_pos in iter_lexelts(inf):
        calc.add_lemma(lemma_pos, len(lexelt.xpath("instance")))
        calc.report()


@eval.command("lkb-entropy-ambg")
def lkb_entropy_ambg():
    wns = (fiwn_encnt, wordnet)
    for wn in wns:
        ambg_calc = LexAmbgCalc(wn)
        ent_calc = EntropyCalc()
        for lemma_pos in lemma_poses(wn):
            ambg_calc.add_lemma(lemma_pos, 1)
            dist = {}
            has_any = False
            for lemma in wn.lemmas(*lemma_pos):
                cnt = lemma.count()
                if cnt > 0:
                    has_any = True
                dist[lemma.key()] = cnt
            if not has_any:
                continue
            ent_calc.add_dist(dist)
        ambg_calc.report()
        ent_calc.report()


def lemma_poses(wn):
    for pos in WN_UNI_POS_MAP.keys():
        for lemma_name in wn.all_lemma_names(pos):
            yield lemma_name, pos


def fix_border(ax):
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)


@eval.command("plot-lkb-ambgs")
@click.argument("outf", type=click.Path(), required=False)
def plot_lkb_ambgs(outf):
    sides = [(fiwn, Counter()), (wordnet, Counter())]
    xs = []
    weights = []
    labels = ["FiWN", "PWN"]
    bins = 0
    for wn, hist in sides:
        for lemma_name, pos in lemma_poses(wn):
            hist[len(wn.lemmas(lemma_name, pos))] += 1
        ambgs = list(hist.keys())
        xs.append(ambgs)
        weights.append(list(hist.values()))
        bins = max(bins, max(ambgs))
    fig = pl.gcf()
    ax = pl.gca()
    fig.set_size_inches(645.0 / 72, 441.0 / 72)
    ax.hist(x=xs, weights=weights, label=labels, bins=bins, log=True)
    ax.set(xlabel="Ambiguity", ylabel="Lemmas")
    ax.set_xlim(1, 60)
    ax.xaxis.set_minor_locator(MultipleLocator(1))

    ax.legend(loc="upper right")
    ax.set_xticks(list(range(1, 11)) + list(range(15, 60, 5)))
    fix_border(ax)
    # handles, labels = ax.get_legend_handles_labels()
    # fig.legend(handles, labels, loc='upper center')

    if outf:
        pl.savefig(outf, bbox_inches="tight")
    else:
        pl.show()


def lex_ambg_hist_uni(inf, wn):
    hist = Counter()
    for sent in iter_sentences(inf):
        instances = sent.xpath("instance")
        for inst in instances:
            ambg = len(
                wn.lemmas(inst.attrib["lemma"], UNI_POS_WN_MAP[inst.attrib["pos"]])
            )
            hist[ambg] += 1
    return hist


ENG_WSD_CORPORA = [
    "senseval2",
    "senseval3",
    "semeval2007",
    "semeval2013",
    "semeval2015",
]


@eval.command("plot-test-ambgs")
@click.argument("eurosensetestxml", type=click.File("rb"))
@click.argument("stifftestxml", type=click.File("rb"))
@click.argument("engwsdevaldir", type=click.Path())
@click.argument("outf", type=click.Path(), required=False)
def plot_test_ambgs(eurosensetestxml, stifftestxml, engwsdevaldir, outf):
    def mk_kwargs():
        return dict(x=[], weights=[], label=[], histtype="barstacked")

    def add_kwargs(kwargs, inf, wn, label):
        lcs = lex_ambg_hist_uni(inf, wn)
        kwargs["x"].append(list(lcs.keys()))
        kwargs["bins"] = max(max(lcs.keys()), kwargs.get("bins", 0))
        kwargs["weights"].append(list(lcs.values()))
        kwargs["label"].append(label)

    fi_kwargs = mk_kwargs()
    add_kwargs(fi_kwargs, eurosensetestxml, fiwn, "EuroSense")
    add_kwargs(fi_kwargs, stifftestxml, fiwn, "STIFF")
    en_kwargs = mk_kwargs()
    for corpus in ENG_WSD_CORPORA:
        path = list(glob(pjoin(engwsdevaldir, corpus, "*.xml")))[0]
        with open(path, "rb") as inf:
            add_kwargs(en_kwargs, inf, wordnet, corpus)
    fig, (ax1, ax2) = pl.subplots(2, sharex=True, gridspec_kw={"hspace": 0.05})

    fix_border(ax1)
    fix_border(ax2)
    fig.set_size_inches(645.0 / 72, 441.0 / 72)
    ax1.hist(**fi_kwargs)
    ax2.hist(**en_kwargs)
    ax1.set_xlim(1, 49)
    # ax1.label_outer()
    # ax2.label_outer()
    ax1.legend(loc="upper right")
    ax2.legend(loc="upper right")
    ax2.set_xlabel("Ambiguity")
    ax1.set_ylabel("Finnish instances")
    ax2.set_ylabel("English instances")
    ax2.set_xticks(list(range(1, 11)) + list(range(15, 50, 5)))
    ax2.xaxis.set_minor_locator(MultipleLocator(1))

    if outf:
        pl.savefig(outf, bbox_inches="tight")
    else:
        pl.show()


@eval.command("plot-train-entropies")
@click.argument("eurosensetrainxml", type=click.File("rb"))
@click.argument("eurosensetrainkey", type=click.File("rb"))
@click.argument("stifftrainxml", type=click.File("rb"))
@click.argument("stifftrainkey", type=click.File("rb"))
@click.argument("semcorxml", type=click.File("rb"))
@click.argument("semcorkey", type=click.File("rb"))
@click.argument("outf", type=click.Path(), required=False)
def plot_train_entropies(
    eurosensetrainxml,
    eurosensetrainkey,
    stifftrainxml,
    stifftrainkey,
    semcorxml,
    semcorkey,
    outf,
):
    from statsmodels.sandbox.nonparametric import kernels
    from statsmodels.nonparametric.kde import bandwidths

    fig, (ax1, ax2, ax3) = pl.subplots(3, sharex=True, gridspec_kw={"hspace": 0.05})

    def add_to_data(data, dists):
        for dist in dists:
            insts = sum(dist.values())
            h = entropy(dist, insts)
            data.extend((h for _ in range(int(insts + 0.5))))

    # EuroSense/STIFF
    bw = None
    for inf, keyin, ax in [
        (eurosensetrainxml, eurosensetrainkey, ax1),
        (stifftrainxml, stifftrainkey, ax2),
    ]:
        data = []
        add_to_data(data, iter_dists_sup(inf, keyin))
        if bw is None:
            bw = bandwidths.select_bandwidth(data, "scott", kernels.Gaussian)
        sns.distplot(data, kde_kws=dict(bw=bw, gridsize=1000), ax=ax)
    # SemCor
    semcor_vocab = {}
    build_uni_sense_dist(iter_sentences(semcorxml), semcorkey, semcor_vocab)
    data = []
    add_to_data(data, semcor_vocab.values())
    # Plot
    sns.distplot(data, kde_kws=dict(bw=bw, gridsize=1000), ax=ax3)
    ax3.set_xlim(-0.1)
    ax3.set_xlabel("Entropy")
    ax1.set_ylabel("EuroSense instance density")
    ax2.set_ylabel("STIFF instance density")
    ax3.set_ylabel("SemCor instance density")
    fix_border(ax1)
    fix_border(ax2)
    fix_border(ax3)
    ax3.xaxis.set_minor_locator(MultipleLocator(0.1))
    fig.set_size_inches(441.0 / 72, 645.0 / 72)

    if outf:
        pl.savefig(outf, bbox_inches="tight")
    else:
        pl.show()


if __name__ == "__main__":
    eval()
