cp=wsdeval-fin/wsdeval_src/WSD_Unified_Evaluation_Datasets

corpus=$1
truetag=$2

firstguess="`basename $corpus`first.guess.key"
mfeguess="`basename $corpus`mfe.guess.key"
leskguess="`basename $corpus`lesk.guess.key"

echo "First"
pipenv run python baselines.py first $corpus $firstguess
java -cp $cp Scorer $truetag $firstguess

echo "Most frequent based on English"
pipenv run python baselines.py mfe $corpus $mfeguess
java -cp $cp Scorer $truetag $mfeguess

echo "Lesk with fasttext vector averaging"
pipenv run python baselines.py lesk_fasttext $corpus $leskguess
java -cp $cp Scorer $truetag $leskguess
