import sys
import os

from plumbum import local
from plumbum.cmd import cat, zstdmt

python = local[sys.executable]


def add_head(filter_py, pipeline, head):
    if head is not None:
        pipeline = pipeline | python[filter_py, "head", "--sentences", head, "-", "-"]
    return pipeline


def add_zstd(in_path):
    if isinstance(in_path, str) and in_path.endswith(".zst"):
        return zstdmt["-D", "zstd-compression-dictionary", "-d", in_path]
    else:
        return cat[in_path]


def ensure_dir(dirout):
    if not os.path.exists(dirout):
        os.makedirs(dirout, exist_ok=True)
