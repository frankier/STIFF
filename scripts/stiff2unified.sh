#!/usr/bin/env bash

zstdcat -D zstd-compression-dictionary $1 \
| python munge.py stiff-to-unified - - \
| python munge.py unified-split - $2 $3
