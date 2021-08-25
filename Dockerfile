ARG PYTHON_VERSION=3.9.6
ARG POETRY_VERSION=1.1.8
ARG PIP_MIN_VERSION=21.2.4

ARG BASE_IMAGE=python:$PYTHON_VERSION-buster

FROM $BASE_IMAGE AS dependencies

ARG PYTHON_VERSION
ARG POETRY_VERSION
ARG PIP_MIN_VERSION

ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

RUN python -m pip install --upgrade --no-cache-dir 'pip>=$PIP_MIN_VERSION'

RUN apt-get update && apt-get install -y procps curl wget vim tzdata psmisc bash make build-essential \
    \
    && apt-get clean autoclean \
    && apt-get autoremove --yes \
    && rm -rf /var/lib/apt/lists/*

RUN printf "\n. /etc/profile\n" >> /root/.profile
RUN printf "\n. /etc/profile\n" >> /root/.bashrc
RUN printf "\nset mouse=\n" >> /usr/share/vim/vim81/defaults.vim
RUN echo "UTC" > /etc/timezone
ENV TZ=UTC
ENV ENV="/etc/profile"

RUN curl -L -o /tmp/install-poetry.py https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py \
    && POETRY_HOME=/usr/local/lib/poetry python /tmp/install-poetry.py --yes --version $POETRY_VERSION \
    && ln -s /usr/local/lib/poetry/bin/poetry /usr/bin/poetry \
    && ln -s /usr/local/lib/poetry/bin/poetry /usr/local/bin/poetry \
    \
    && poetry config virtualenvs.create false \
    && poetry config virtualenvs.in-project false \
    \
    && poetry --version

ENV VIRTUAL_ENV=/usr/local
ENV POETRY_ACTIVE=1

FROM dependencies as development

RUN mkdir -p /app

COPY mypy.ini tox.ini /app/
COPY LICENSE README.rst CHANGES.rst Makefile /app/
COPY tomodachi.py /app/
COPY pyproject.toml poetry.lock /app/
COPY tomodachi /app/tomodachi
COPY tests /app/tests
COPY examples /app/examples

WORKDIR /app
RUN make install

CMD ["/bin/bash"]
