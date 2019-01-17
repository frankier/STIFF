FROM frankierr/finntk:requirements

RUN apk --no-cache add openssl-dev freetype-dev libpng-dev openblas-dev \
	musl-dev openblas libxml2-dev xmlsec-dev zstd
RUN apk --no-cache add opencc opencc-dev --update-cache --repository http://dl-3.alpinelinux.org/alpine/edge/testing/ --allow-untrusted
RUN ln -s locale.h /usr/include/xlocale.h
COPY . /stiff
WORKDIR /stiff

RUN apk --no-cache add curl
RUN ln -sf /usr/bin/python3 /usr/local/bin/python
RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python3
RUN pip3 install https://download.pytorch.org/whl/cu100/torch-1.0.0-cp37-cp37m-linux_x86_64.whl
RUN ~/.poetry/bin/poetry config settings.virtualenvs.create false
RUN ~/.poetry/bin/poetry install
RUN python3 -m stiff.scripts.post_install

# Install WordNet
RUN python3 -c "from nltk import download as d; d('wordnet'); d('omw'); d('punkt')"
