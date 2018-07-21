corpus=$1
truetag=$2

firstguess="guess/`basename $corpus`first.guess.key"
mfeguess="guess/`basename $corpus`mfe.guess.key"
leskfasttextguess="guess/`basename $corpus`lesk.fasttext.guess.key"
leskfilterfasttextguess="guess/`basename $corpus`lesk.fasttext.filter.guess.key"
leskconceptnetguess="guess/`basename $corpus`lesk.conceptnet.guess.key"
leskfilterconceptnetguess="guess/`basename $corpus`lesk.conceptnet.filter.guess.key"

mkdir -p guess

echo "First"
pipenv run python baselines.py first $corpus $firstguess
java Scorer $truetag $firstguess

echo "Most frequent based on English"
pipenv run python baselines.py mfe $corpus $mfeguess
java Scorer $truetag $mfeguess

echo "Lesk with fasttext vector averaging"
pipenv run python baselines.py lesk_fasttext $corpus $leskfasttextguess
java Scorer $truetag $leskfasttextguess

echo "Lesk with fasttext vector averaging + wn filtering"
pipenv run python baselines.py lesk_fasttext --wn-filter $corpus $leskfilterfasttextguess
java Scorer $truetag $leskfilterfasttextguess

echo "Lesk with conceptnet vector averaging"
pipenv run python baselines.py lesk_conceptnet $corpus $leskconceptnetguess
java Scorer $truetag $leskconceptnetguess

echo "Lesk with conceptnet vector averaging + wn filtering"
pipenv run python baselines.py lesk_conceptnet --wn-filter $corpus $leskfilterconceptnetguess
java Scorer $truetag $leskfilterconceptnetguess
