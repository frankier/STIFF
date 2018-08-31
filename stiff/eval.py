from os.path import join as pjoin


def get_eval_paths(evaldir):
    ps = {}
    for partition in ("test", "train"):
        ps[partition] = {
            "unified": pjoin(evaldir, partition + ".xml"),
            "unikey": pjoin(evaldir, partition + ".key"),
            "sup": pjoin(evaldir, partition + ".sup.xml"),
            "supkey": pjoin(evaldir, partition + ".sup.key"),
            "suptag": pjoin(evaldir, partition + ".sup.tag.xml"),
            "supseg": pjoin(evaldir, partition + ".sup.seg.xml"),
        }
    return ps
