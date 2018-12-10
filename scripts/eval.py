from lxml import etree
import click
from stiff.utils.anns import get_ann_pos, get_ann_pos_dict
from stiff.utils.xml import cb_to_iter, chunk_cb, eq_matcher, iter_sentences
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
                    "GUESS ended before all GOLD sentences were found"
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


def iter_sent_to_pairs(sent_iter):
    for sent in sent_iter:
        yield sent.attrib["id"], sent


def iter_sentence_id_pairs(fp):
    """
    Like iter_sentences(...), but returns also sentence IDs, in the case of
    OpenSubtitles2018 adjusted to include also subtitle information.
    """
    # Detect OpenSubtitles2018
    stream = etree.iterparse(fp, events=("start", "end"))
    opensubs18 = None
    for idx, (event, element) in zip(range(100), stream):
        if element.tag == "corpus":
            opensubs18 = element.attrib["source"] == "OpenSubtitles2018"
            break
    else:
        assert False, "No <corpus ...> tag found."
    if opensubs18:

        def sentence_chunker(cb):
            chunk_cb(stream, eq_matcher("sentence"), cb)

        for event, element in stream:
            if event == "start" and element.tag == "subtitle":
                sources = " ".join(element.attrib["sources"].split("; "))
                imdb = element.attrib["imdb"]
                for sent in cb_to_iter(sentence_chunker)():
                    full_id = "{}; {}; {}".format(sources, imdb, sent.attrib["id"])
                    yield full_id, sent
    else:
        return iter_sent_to_pairs(iter_sentences(fp))


def anns_to_set(anns):
    return {(int(get_ann_pos_dict(ann)["token"]), ann.text) for ann in anns}


def calc_pr(tp, fp, fn):
    if tp == 0:
        return 0, 0, 0
    p = tp / (tp + fp)
    r = tp / (tp + fn)
    return (p, r, 2 * p * r / (p + r))


def pr_one(gold_etree, guess_fp, trace_individual=False):
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
        gold_ann_set = anns_to_set(gold_anns)
        guess_ann_set = anns_to_set(guess_anns)
        tp = len(gold_ann_set & guess_ann_set)
        fp = len(guess_ann_set - gold_ann_set)
        fn = len(gold_ann_set - guess_ann_set)
        if trace_individual:
            print("#{:02d} {}".format(idx, sent_id))
            print(
                "P: {}, R: {}, F_1: {}, tp: {}, fp: {}, fn: {}",
                *calc_pr(tp, fp, fn),
                tp,
                fp,
                fn,
            )
        total_tp += tp
        total_fp += fp
        total_fn += fn
    return calc_pr(total_tp, total_fp, total_fn)


@eval.command("pr")
@click.argument("gold", type=click.File("rb"), nargs=1)
@click.argument("guess", type=click.File("rb"), nargs=-1)
@click.option("--trace-individual/--no-trace-individual", default=False)
def pr(gold, guess, trace_individual):
    gold_etree = etree.parse(gold)
    for guess_fp in guess:
        print(guess_fp)
        print(pr_one(gold_etree, guess_fp, trace_individual))


@eval.command("pr-eval")
@click.argument("gold", type=click.File("rb"))
@click.argument("eval", type=click.Path())
@click.option("--plot/--no-plot")
@click.option("--trace-individual/--no-trace-individual", default=False)
def pr_eval(gold, eval, plot, trace_individual):
    names = []
    prs = []
    gold_etree = etree.parse(gold)
    for entry in listdir(eval):
        name = entry.rsplit(".", 1)[0]
        if trace_individual:
            print(name)
        names.append(name)
        prs.append(pr_one(gold_etree, open(pjoin(eval, entry), "rb"), trace_individual))
    if plot:
        import matplotlib.pyplot as plt
        from adjustText import adjust_text
        import pareto

        nondominated = pareto.eps_sort(prs, [0, 1], maximize_all=True, attribution=True)
        nondominated_idxs = [nd[-1] for nd in nondominated]
        plt.xlabel("Precision")
        plt.ylabel("Recall")
        nondom_ps = []
        nondom_rs = []
        dom_ps = []
        dom_rs = []
        for idx, pr in enumerate(prs):
            if idx in nondominated_idxs:
                nondom_ps.append(pr[0])
                nondom_rs.append(pr[1])
            else:
                dom_ps.append(pr[0])
                dom_rs.append(pr[1])
        plt.scatter(dom_ps, dom_rs, marker="o", c="k")
        plt.scatter(nondom_ps, nondom_rs, marker="D", c="b")
        texts = []
        for name, (p, r, _f1) in zip(names, prs):
            texts.append(plt.text(p, r, name, ha="center", va="center"))
        adjust_text(texts, arrowprops=dict(arrowstyle="->", color="red"))
        plt.show()
    else:
        for name, pr in zip(names, prs):
            print(name, pr[0], pr[1], pr[2])


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
            ann_poses = []
            ann_pos_idx = set()
            for ann in anns:
                tok, tok_len = get_ann_pos(ann)
                ann_index.setdefault(tok, []).append(ann)
                ann_pos_idx.add((tok, tok_len))
                idxes = []
                for idx in range(tok, tok + tok_len):
                    cov_map[idx] += 1
                    idxes.append(idx)
                ann_poses.append(idxes)
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
