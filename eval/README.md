# Evaluation framework

This directory contains the evaluation framework. The scorer program is the
same as the one used in *Word Sense Disambiguation: A Unified Evaluation
Framework and Empirical Comparison.*. First you need to obtain it:

    ./get_scorer.sh

## Running the baselines

    ./run_eval_baselines.sh /path/to/eval.xml /path/to/eval.key

## Running the UKB experiments

First set the environment variable UKB_PATH to where your compiled copy of UKB
is located.

    cd ukb-eval && ./prepare_wn30graph.sh && cd ..
    pipenv run python mkwndict.py --en-synset-ids > wndict.en.txt
    pipenv run python ukb.py run_all /path/to/eval/corpus.xml ukb-eval/wn30/wn30g.bin wndict.txt /path/to/eval/corpus.key
