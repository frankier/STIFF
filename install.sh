poetry install
poetry run python3 -c "from nltk import download as d; d('wordnet'); d('omw'); d('punkt')"
poetry run python3 -m stiff.scripts.post_install
