FROM python:3.13-slim AS builder

LABEL maintainer="MetaboLights (metabolights-help @ ebi.ac.uk)"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN uv sync --locked --group=test --group=dev

ENV PYTHONPATH=/app

EXPOSE 7070
CMD ["uv", "run", "--no-project",  "/app/mhd_ws/run/rest_api/mhd/main.py"]
