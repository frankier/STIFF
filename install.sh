pipenv --site-packages
pipenv install
pipenv run python3 -c "from nltk import download as d; d('wordnet'); d('omw'); d('punkt')"
pipenv run python3 scripts/patch_cwn.py
pipenv run python3 scripts/fetch_omw_wikt.py
pipenv run python3 scripts/fetch_opensubtitles2018.py
