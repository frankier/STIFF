#!/usr/bin/env bash

python scripts/filter.py join \
	<(python scripts/man_ann.py opensubs18 $1 -) \
	<(python scripts/pipeline.py man-ann-eurosense $2 -) \
	<(python scripts/pipeline.py man-ann-tdt $3 -) \
	$4
