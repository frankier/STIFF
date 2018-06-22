corpus=$1
truetag=$2

firstguess="guess/`basename $corpus`first.guess.key"
mfeguess="guess/`basename $corpus`mfe.guess.key"
leskguess="guess/`basename $corpus`lesk.guess.key"

mkdir -p guess

echo "First"
pipenv run python baselines.py first $corpus $firstguess
java Scorer $truetag $firstguess

echo "Most frequent based on English"
pipenv run python baselines.py mfe $corpus $mfeguess
java Scorer $truetag $mfeguess

echo "Lesk with fasttext vector averaging"
pipenv run python baselines.py lesk_fasttext $corpus $leskguess
java Scorer $truetag $leskguess
