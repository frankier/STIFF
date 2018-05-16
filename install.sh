pipenv --site-packages
pipenv install
pipenv run python3 -c "from nltk import download as d; d('wordnet'); d('omw'); d('punkt')"
