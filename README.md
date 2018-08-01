# STIFF - Sense Tagged Instances For Finnish

Work In Progress

## Set up

You will need HFST and OMorFi installed globally before beginning. The reason
for this is neither are currently PyPI installable. You will also need pipenv.
You can then run

    $ ./install.sh

## Example conversions

### Sampling EuroSense and convert to unified

You will need to set the environment variable BABEL2WN_MAP as the path to a TSV
mapping from BabelNet synsets to WordNet synsets. This file can be obtained
from a BabelNet dump + following the instructions at
https://github.com/frankier/babelnet-lookup

    pipenv run python pipeline.py eurosense2unified --head 1000 \
      /path/to/eurosense.v1.0.high-precision.xml eurosense.unified.sample.xml \
      eurosense.unified.sample.key

### Making STIFF, sampling/filtering and converting to unified

    pipenv run python fetch_opensubtitles2018.py cmn-fin
    ./mk_stiff.sh
    pipenv run python pipeline.py proc-stiff simple --head 1000 stiff.raw.xml.zstd stiff.simplefiltered.sample.xml.zstd
    ./stiff2unified.sh stiff.simplefiltered.sample.xml.zstd stiff.unified.sample.xml stiff.unified.sample.key


## Organisation & usage

For help using the tools, try running with `--help`. The main entry points are
in `scripts`.

Innards
    `scripts/tag.py`: Produce an unfiltered STIFF
    `scripts/filter.py`: Filter STIFF according to various criteria
    `scripts/munge.py`: Convert between different corpus/stream formats

Wrappers:
    `scripts/mk_stiff.sh`: Produce an unfiltered STIFF with the default settings
    `scripts/stiff2unified.sh`: Convert from STIFF format to the unified format
    `scripts/pipeline.py`: Various pipelines composing multiple layers of filtering/conversion
