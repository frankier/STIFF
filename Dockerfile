FROM frankierr/finntk:requirements

RUN apk --no-cache add openssl-dev freetype-dev libpng-dev openblas-dev \
	musl-dev openblas libxml2-dev xmlsec-dev zstd
RUN apk --no-cache add opencc opencc-dev --update-cache --repository http://dl-3.alpinelinux.org/alpine/edge/testing/ --allow-untrusted
RUN ln -s locale.h /usr/include/xlocale.h
COPY . /stiff
WORKDIR /stiff
RUN pipenv install --deploy --system
RUN python3 -m stiff.scripts.post_install

# Install WordNet
RUN python3 -c "from nltk import download as d; d('wordnet'); d('omw'); d('punkt')"
