import os
from urllib.request import urlretrieve
import zipfile
import shutil
from plumbum.cmd import patch

from stiff.data import get_data_path


print("Fetching and patching cmn")
os.chdir(get_data_path())
fn, headers = urlretrieve("http://compling.hss.ntu.edu.sg/omw/wns/cmn.zip")
assert headers["Content-Type"] == "application/zip"
zip = zipfile.ZipFile(fn, "r")
old = zip.open("cow/wn-data-cmn.tab")
with open("wn-data-cmn-fixed.tab", "wb") as f_out:
    shutil.copyfileobj(old, f_out)

patch("wn-data-cmn-fixed.tab", "data/wn-data-cmn.diff")
