#!/usr/bin/env bash

python filter.py lang fi $1 - \
| python munge.py babelnet-lookup - \
    /home/frankier/sourcestmp/babelnet-lookup/babelwnmap.clean.tsv - \
| python filter.py rm-empty - - \
| python munge.py eurosense-to-unified - - \
| python munge.py unified-split - $2 $3
