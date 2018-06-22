import click
from urllib.request import urlretrieve
from urllib.parse import urlparse
from os import makedirs
import zipfile
from os.path import join as pjoin
import gzip
import shutil

ROOT = "http://opus.nlpl.eu/download/OpenSubtitles2018/"

PAIRS = [("fi", "zh_cn"), ("fi", "zh_tw")]


def get_zip(url, dest_dir):
    fn, headers = urlretrieve(url)
    assert headers["Content-Type"] == "application/zip"
    zip = zipfile.ZipFile(fn, "r")
    zip.extractall(dest_dir)
    zip.close()


def get_gzip(url, dest_dir):
    fn, headers = urlretrieve(url)
    assert headers["Content-Type"] in ("application/gzip", "application/x-gzip")
    basename = urlparse(url).path.split("/")[-1]
    assert basename.endswith(".gz")
    basename = basename[:-3]
    with gzip.open(fn, "rb") as f_in:
        with open(pjoin(dest_dir, basename), "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)


@click.command("fetch")
@click.argument("dir_name")
def fetch_ost2018(dir_name):
    print("Fetching:")
    makedirs(dir_name, exist_ok=True)
    for lang1, lang2 in PAIRS:
        pair = "{}-{}".format(lang1, lang2)
        full_dir = pjoin(dir_name, pair)
        makedirs(full_dir, exist_ok=True)

        # Untokenised
        print("Untokenised {}".format(pair))
        get_zip("{}{}.txt.zip".format(ROOT, pair), full_dir)

        # Tokenised
        print("Tokenised {}".format(pair))
        base_url = "{}{}/".format(ROOT, pair)
        for lang in [lang1, lang2]:
            get_gzip("{}c.clean.{}.gz".format(base_url, lang), full_dir)

        # Alignments
        print("Sentence alignments {}".format(pair))
        get_gzip("{}ids.gz".format(base_url), full_dir)
        print("Word alignments {}".format(pair))
        get_gzip("{}model/aligned.grow-diag-final-and.gz".format(base_url), full_dir)


if __name__ == "__main__":
    fetch_ost2018()
