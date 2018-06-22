corpus=$1
truetag=$2

firstguess="`basename $corpus`first.guess.key"
mfeguess="`basename $corpus`mfe.guess.key"
leskguess="`basename $corpus`lesk.guess.key"

echo "First"
pipenv run python baselines.py first $corpus $firstguess
java Scorer $truetag $firstguess

echo "Most frequent based on English"
pipenv run python baselines.py mfe $corpus $mfeguess
java Scorer $truetag $mfeguess

echo "Lesk with fasttext vector averaging"
pipenv run python baselines.py lesk_fasttext $corpus $leskguess
java Scorer $truetag $leskguess
