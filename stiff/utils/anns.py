from urllib.parse import parse_qsl


def get_ann_pos(ann):
    anchor_poses = ann.attrib["anchor-positions"].split()
    assert len(anchor_poses) == 1
    anchor_pos_str = anchor_poses[0]
    anchor_pos = dict(parse_qsl(anchor_pos_str))
    tok = int(anchor_pos["token"])
    tok_len = int(anchor_pos["token-length"]) if "token-length" in anchor_pos else 1
    return tok, tok_len
