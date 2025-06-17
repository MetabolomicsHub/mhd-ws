FROM python:3.13-slim-bullseye AS builder
LABEL maintainer="MetaboLights (metabolights-help @ ebi.ac.uk)"

RUN apt-get clean && apt-get -y update && apt-get -y install build-essential python3-dev python3-pip libpq-dev libglib2.0-0 libsm6 libxrender1 libxext6

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=1 
ENV POETRY_VIRTUALENVS_CREATE=1
ENV POETRY_CACHE_DIR=/tmp/poetry_cache
ENV POETRY_HOME=/opt/poetry
WORKDIR /app

RUN pip3 install --upgrade pip 
RUN pip3 install poetry
RUN poetry --version

COPY pyproject.toml .
COPY poetry.lock .
RUN touch README.md


RUN poetry install --no-root && rm -rf $POETRY_CACHE_DIR


FROM python:3.13-slim-bullseye AS runner
LABEL maintainer="MetaboLights (metabolights-help @ ebi.ac.uk)"

RUN apt-get -y update \
    && apt-get -y install wget curl zip libglib2.0-0 libsm6 libxrender1 libxext6 libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get -y autoremove --purge


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV VIRTUAL_ENV=/app/.venv
ENV PATH=/app/.venv/bin:$PATH
ENV PYTHONPATH=/app

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY . /app

WORKDIR /app

EXPOSE 7070
RUN chmod +x mhd_ws/run/rest_api/mhd/main.py

CMD ["python", "mhd_ws/run/rest_api/mhd/main.py"]
