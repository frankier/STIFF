FROM frankierr/finntk

COPY . /stiff
WORKDIR /stiff
RUN pipenv install --deploy --system
