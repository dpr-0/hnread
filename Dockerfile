# syntax=docker/dockerfile:1
FROM python:3.10.5-slim-bullseye as builder

WORKDIR /app
COPY  pyproject.toml ./

RUN python -m venv --copies venv
ENV PATH="/app/venv/bin:$PATH"

RUN pip install "poetry==1.1.13" --no-cache-dir && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-root --no-interaction --no-ansi && \
    pip uninstall --yes poetry && \
    pip cache purge && \
    rm -rf ~/.cache/pypoetry/{cache,artifacts}

FROM python:3.10.5-slim-bullseye as prod

COPY --from=builder /app/venv app/venv
ENV PATH="/app/venv/bin:$PATH"

WORKDIR /app
COPY bot.py ./
COPY hnread ./hnread

CMD ["python", "bot.py"]
