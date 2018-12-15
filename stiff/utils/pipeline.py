import sys
import os

from plumbum import local

python = local[sys.executable]


def add_head(filter_py, pipeline, head):
    if head is not None:
        pipeline = pipeline | python[filter_py, "head", "--sentences", head, "-", "-"]
    return pipeline


def ensure_dir(dirout):
    if not os.path.exists(dirout):
        os.makedirs(dirout, exist_ok=True)
