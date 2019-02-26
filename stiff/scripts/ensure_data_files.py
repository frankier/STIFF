# XXX: Bad workaround for lack of data_files in poetry

import os
from urllib.request import urlretrieve

from stiff.data import get_data_path

os.chdir(get_data_path())
for fn in ["t2s_char.json", "wn-data-cmn.diff"]:
    if os.path.exists(fn):
        continue
    fn_dl, headers = urlretrieve(
        "https://raw.githubusercontent.com/frankier/STIFF/62773e76ded69c35ba7cc15e7687091b40448951/stiff/data/"
        + fn,
        fn,
    )
