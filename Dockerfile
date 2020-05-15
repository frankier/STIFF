FROM registry.gitlab.com/frankier/finntk/requirements-deb:latest

RUN apt-get update && apt-get install -y \
	libssl-dev libfreetype6-dev libpng-dev libopenblas-dev \
	musl-dev libopenblas-base libxml2-dev libxmlsec1-dev zstd \
	opencc libopencc-dev curl texlive texlive-xetex python3-venv

RUN ln -sf /usr/bin/python3 /usr/local/bin/python
RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python3
RUN pip3 install https://download.pytorch.org/whl/cu100/torch-1.0.0-cp37-cp37m-linux_x86_64.whl
RUN ~/.poetry/bin/poetry config virtualenvs.create false

# Slow changing stuff
RUN mkdir /stiff/
WORKDIR /stiff
COPY poetry.lock pyproject.toml /stiff/
RUN mkdir /stiff/stiff && touch /stiff/stiff/__init__.py
RUN ~/.poetry/bin/poetry install --no-interaction
RUN python3 -c "from nltk import download as d; d('wordnet'); d('omw'); d('punkt')"

# Fast changing stuff
COPY . /stiff
RUN python3 -m stiff.scripts.post_install

# Temp quickfix
RUN echo "/usr/local/lib/python3.7/site-packages/" > "/usr/local/lib/python3.7/dist-packages/site.pth"
