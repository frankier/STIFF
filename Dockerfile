FROM frankierr/finntk:requirements

RUN apk --no-cache add openssl-dev freetype-dev libpng-dev openblas-dev \
	musl-dev openblas libxml2-dev xmlsec-dev zstd
RUN apk --no-cache add opencc opencc-dev --update-cache --repository http://dl-3.alpinelinux.org/alpine/edge/testing/ --allow-untrusted
RUN ln -s locale.h /usr/include/xlocale.h
COPY . /stiff
WORKDIR /stiff
RUN pipenv install --deploy --system
RUN python3 scripts/patch_cwn.py
RUN python3 scripts/fetch_omw_wikt.py

# Install WordNet
RUN python3 -c "from nltk import download as d; d('wordnet'); d('omw'); d('punkt')"
