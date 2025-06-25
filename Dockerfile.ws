FROM python:3.13-slim AS builder

LABEL maintainer="MetaboLights (metabolights-help @ ebi.ac.uk)"

# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates libglib2.0-0

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"


# RUN apt-get clean && apt-get -y update && apt-get -y install build-essential python3-dev python3-pip libpq-dev libglib2.0-0 libsm6 libxrender1 libxext6

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/app/.venv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --locked


FROM python:3.13-slim AS runner

LABEL maintainer="MetaboLights (metabolights-help @ ebi.ac.uk)"

# RUN apt-get -y update \
#     && apt-get -y upgrade \
#     && apt-get -y install wget curl zip libglib2.0-0 libsm6 libxrender1 libxext6 libpq-dev \
#     && rm -rf /var/lib/apt/lists/* \
#     && apt-get -y autoremove --purge


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV VIRTUAL_ENV=/app/.venv
ENV PATH=/app/.venv/bin:$PATH
ENV PYTHONPATH=/app

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY . /app

WORKDIR /app

RUN chmod +x mhd_ws/run/rest_api/mhd/main.py

EXPOSE 7070
CMD ["python", "mhd_ws/run/rest_api/mhd/main.py"]
