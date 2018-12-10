from stiff.utils import parse_qs_single


def get_ann_pos_dict(ann):
    anchor_poses = ann.attrib["anchor-positions"].split()
    assert len(anchor_poses) == 1
    anchor_pos_str = anchor_poses[0]
    return parse_qs_single(anchor_pos_str)


def get_ann_pos(ann):
    anchor_pos = get_ann_pos_dict(ann)
    tok = int(anchor_pos["token"])
    tok_len = int(anchor_pos["token-length"]) if "token-length" in anchor_pos else 1
    return tok, tok_len
