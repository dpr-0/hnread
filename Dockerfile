# syntax=docker/dockerfile:1
FROM python:3.10-slim-buster
WORKDIR /app
COPY makefile bot.py pyproject.toml ./
COPY hnread ./hnread
RUN pip install "poetry==1.1.13" --no-cache-dir \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev --no-root --no-interaction --no-ansi \
    && rm -rf ~/.cache/pypoetry/{cache,artifacts}
CMD ["python", "bot.py"]
