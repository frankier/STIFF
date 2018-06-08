#!/usr/bin/env bash

python tag.py cmn-fin - \
| zstdmt -D zstd-compression-dictionary - -o stiff.raw.xml.zstd
