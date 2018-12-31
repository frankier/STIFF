# STIFF - Sense Tagged Instances For Finnish

<p align="center">
<a href="https://gitlab.com/frankier/STIFF/pipelines"><img alt="pipeline status" src="https://gitlab.com/frankier/STIFF/badges/master/pipeline.svg" /></a>
</p>

This repository contains code to automatically create a tagged sense corpus
from OpenSubtitles2018. It also contains a lot of corpora wrangling code, most
notably code to convert (the CC-NC licensed)
[EuroSense](http://lcl.uniroma1.it/eurosense/) into a format usable by
[finn-wsd-eval](https://github.com/frankier/finn-wsd-eval).

## Set up

You will need HFST and OMorFi installed globally before beginning. The reason
for this is neither are currently PyPI installable. You will also need pipenv.
You can then run

    $ ./install.sh

## Example processing & conversion pipelines

Both the following pipelines first create a corpus tagged in the unified
format, which consists of an `xml` and `key` file, and then create a directory
consisting of the files needed by
[finn-wsd-eval](https://github.com/frankier/finn-wsd-eval).

### STIFF Pipeline

#### Fetch OpenSubtitles2018

    pipenv run python scripts/fetch_opensubtitles2018.py cmn-fin

#### Make raw STIFF

    pipenv run python scripts/pipeline.py mk-stiff cmn-fin stiff.raw.xml.zst

#### Make recommended STIFF variant + convert ➡️ Unified

    pipenv run python scripts/variants.py proc bilingual-precision-4 stiff.raw.xml.zst stiff.bp4.xml.zst
    ./stiff2unified.sh stiff.bp4.xml.zst stiff.unified.bp4.xml stiff.unified.bp4.key

### EuroSense Pipeline

#### EuroSense ➡️ Unified

You will first need to obtain EuroSense. Since there are some language tagging
issues with the original, I currently recommend you use [a version I have
attempted to fix](https://github.com/frankier/eurosense).

You will next need to set the environment variable BABEL2WN_MAP as the path to a TSV
mapping from BabelNet synsets to WordNet synsets. You can either:

1. Obtain the BabelNet indices by following [these
   instructions](https://babelnet.org/guide#access) and dump out the TSV by
   following the instructions at https://github.com/frankier/babelnet-lookup
2. If you are affiliated with a research institution, I have permission to send
   you the TSV file, but you must send me a direct communication from your
   institutional email address. (Please shortly state your position/affiliation
   and non-commercial research use in the email so there is a record.)
3. Alternatively (subject to the same conditions) if you prefer, I can just
   send you eurosense.unified.sample.xml eurosense.unified.sample.key

Then run:

    pipenv run python scripts/pipeline.py eurosense2unified \
      /path/to/eurosense.v1.0.high-precision.xml eurosense.unified.sample.xml \
      eurosense.unified.sample.key

### Make STIFF or EuroSense into data for finn-wsd-eval

This makes a directory usable by
[finn-wsd-eval](https://github.com/frankier/finn-wsd-eval).

Run:

    pipenv run python scripts/pipeline.py unified-to-eval \
      /path/to/stiff-or-eurosense.unified.xml /path/to/stiff-or-eurosense.unified.key \
      stiff-or-eurosense.eval/

### Make STIFF and EuroSense P/R plot

First obtain [finn-man-ann](https://github.com/frankier/finn-man-ann).

#### Gather STIFF eval data

    pipenv run python scripts/variants.py eval /path/to/stiff.raw.zst stiff-eval-out
    pipenv run python scripts/eval.py pr-eval --score=tok <(pipenv run python scripts/munge.py man-ann-select --source=OpenSubtitles2018 /path/to/finn-man-ann/ann.xml -) stiff-eval-out stiff-eval.csv

#### Gather EuroSense eval data

    pipenv run python scripts/munge.py man-ann-select --source=europarl /path/to/finn-man-ann/ann.xml - | pipenv run python scripts/munge.py lemma-to-synset - man-ann-europarl.xml
    mkdir eurosense-pr
    mv /path/to/eurosense/high-precision.xml eurosense-pr/EP.xml
    mv /path/to/eurosense/high-coverage.xml eurosense-pr/EC.xml
    pipenv run python scripts/eval.py pr-eval --score=tok man-ann-europarl.xml eurosense-pr europarl.csv

#### Plot on common axis

Warning, plot may be misleading...

    pipenv run python scripts/eval.py pr-plot stiff-eval.csv europarl.csv

## Organisation & usage

For help using the tools, try running with `--help`. The main entry points are
in `scripts`.

### Innards

 * `scripts/tag.py`: Produce an unfiltered STIFF
 * `scripts/filter.py`: Filter STIFF according to various criteria
 * `scripts/munge.py`: Convert between different corpus/stream formats

### Wrappers

 * `scripts/stiff2unified.sh`: Convert from STIFF format to the unified format
 * `scripts/pipeline.py`: Various pipelines composing multiple layers of filtering/conversion
