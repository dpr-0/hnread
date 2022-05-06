# syntax=docker/dockerfile:1
FROM python:3.9-slim-buster
WORKDIR /app
RUN pip install "poetry==1.1.13"
COPY . .
RUN poetry config virtualenvs.create false \ 
    && poetry install --no-dev --no-root
CMD ["python", "bot.py"]
