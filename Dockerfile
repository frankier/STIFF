FROM registry.gitlab.com/frankier/finntk/requirements-deb:latest

RUN apt-get update && apt-get install -y \
	libssl-dev libfreetype6-dev libpng-dev libopenblas-dev \
	musl-dev libopenblas-base libxml2-dev libxmlsec1-dev zstd \
	opencc libopencc-dev curl
COPY . /stiff
WORKDIR /stiff

RUN ln -sf /usr/bin/python3 /usr/local/bin/python
RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python3
RUN pip3 install https://download.pytorch.org/whl/cu100/torch-1.0.0-cp37-cp37m-linux_x86_64.whl
RUN ~/.poetry/bin/poetry config settings.virtualenvs.create false
RUN ~/.poetry/bin/poetry install
RUN python3 -m stiff.scripts.post_install

# Install WordNet
RUN python3 -c "from nltk import download as d; d('wordnet'); d('omw'); d('punkt')"
