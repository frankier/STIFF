#!/bin/bash

# Do not change anything below
abspath_to_ukb=$(realpath ${UKB_PATH})
script_dir=${abspath_to_ukb}/../scripts

###########################
# Create WN30 WordNet graph
###########################
install -d wn30
cd wn30
# download and extract
wget -q http://wordnetcode.princeton.edu/3.0/WordNet-3.0.tar.gz
tar xzf WordNet-3.0.tar.gz
wget -q http://wordnetcode.princeton.edu/glosstag-files/WordNet-3.0-glosstag.tar.bz2
tar xjf WordNet-3.0-glosstag.tar.bz2 
# create ukb relation files from source (including gloss relations)
perl ${script_dir}/wnet2graph.pl WordNet-3.0/dict/* > wn30_rel.txt
perl ${script_dir}/wnetgloss2graph.pl WordNet-3.0/dict/index.sense  WordNet-3.0/glosstag/merged > wn30_gloss_rel.txt
# compile graph
cat wn30_rel.txt wn30_gloss_rel.txt | ${abspath_to_ukb}/compile_kb -o wn30g.bin --note "wn30_rel.txt wn30_gloss_rel.txt" -
