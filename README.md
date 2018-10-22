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

### STIFF Pipeline (WIP)

e.g.

    pipenv run python scripts/fetch_opensubtitles2018.py cmn-fin
    pipenv run python scripts/pipeline.py mk-stiff cmn-fin stiff.raw.xml.zstd
    pipenv run python scripts/pipeline.py proc-stiff simple stiff.raw.xml.zstd stiff.simplefiltered.sample.xml.zstd
    ./stiff2unified.sh stiff.simplefiltered.sample.xml.zstd stiff.unified.sample.xml stiff.unified.sample.key

### EuroSense Pipeline

#### EuroSense ➡️ Unified

You will need to set the environment variable BABEL2WN_MAP as the path to a TSV
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

#### Unified ➡️ Eval

Run:

    pipenv run python scripts/pipeline.py unified-to-eval \
      /path/to/eurosense.unified.xml /path/to/eurosense.unified.key \
      eurosense.eval/

## Organisation & usage

For help using the tools, try running with `--help`. The main entry points are
in `scripts`.

Innards
    `scripts/tag.py`: Produce an unfiltered STIFF
    `scripts/filter.py`: Filter STIFF according to various criteria
    `scripts/munge.py`: Convert between different corpus/stream formats

Wrappers:
    `scripts/stiff2unified.sh`: Convert from STIFF format to the unified format
    `scripts/pipeline.py`: Various pipelines composing multiple layers of filtering/conversion
