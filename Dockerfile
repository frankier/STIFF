FROM frankierr/finntk:requirements

COPY . /stiff
WORKDIR /stiff
RUN pipenv install --deploy --system
