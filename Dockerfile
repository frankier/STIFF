FROM frankierr/finntk:requirements

RUN apk --no-cache add openssl-dev freetype-dev libpng-dev openblas-dev musl-dev openblas
RUN ln -s locale.h /usr/include/xlocale.h
COPY . /stiff
WORKDIR /stiff
RUN pipenv install --deploy --system
