from urllib.parse import parse_qsl


def parse_qs_single(qs):
    return dict(parse_qsl(qs))


def wnlemma_to_analy_lemma(wnlemma):
    return wnlemma.lower().replace("_", " ").strip("-")
