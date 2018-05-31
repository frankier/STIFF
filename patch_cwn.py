from urllib.request import urlretrieve
import zipfile
import shutil
from plumbum.cmd import patch
from nltk.corpus import wordnet


fn, headers = urlretrieve("http://compling.hss.ntu.edu.sg/omw/wns/cmn.zip")
assert headers['Content-Type'] == 'application/zip'
zip = zipfile.ZipFile(fn, 'r')
old = zip.open('cow/wn-data-cmn-fixed.tab')
with open('wn-data-cmn.tab', 'wb') as f_out:
    shutil.copyfileobj(old, f_out)

patch('wn-data-cmn-fixed.tab', 'wn-data-cmn.diff')
