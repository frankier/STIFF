#!/usr/bin/env bash

script_path=$(dirname "$0")

python $script_path/tag.py $1 - \
| zstdmt -D zstd-compression-dictionary - -o $2
