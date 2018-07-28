#!/usr/bin/env bash

script_path=$(dirname "$0")

python $script_path/tag.py cmn-fin - \
| zstdmt -D zstd-compression-dictionary - -o stiff.raw.xml.zstd
