import os
from os.path import dirname, join as pjoin
from urllib.request import urlretrieve
import zipfile
import shutil

from stiff.data import get_data_path


print("Fetching Wiktionary derived data")
os.chdir(get_data_path())
fn, headers = urlretrieve("http://compling.hss.ntu.edu.sg/omw/wn-wikt.zip")
assert headers["Content-Type"] == "application/zip"
zip = zipfile.ZipFile(fn, "r")
for tab in ["wn-wikt-cmn.tab", "wn-wikt-fin.tab"]:
    old = zip.open("data/wikt/" + tab)
    with open(tab, "wb") as f_out:
        shutil.copyfileobj(old, f_out)
