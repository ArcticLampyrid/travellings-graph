FROM python:3.12-alpine as builder
RUN pip install poetry==1.8.2
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache
WORKDIR /app
COPY . .
RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --no-dev --no-root
COPY ./travellings_graph ./travellings_graph
RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --no-dev

FROM python:3.12-alpine as runtime
ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"
COPY --from=builder /app /app
RUN mkdir -p /app/data
WORKDIR /app/data
EXPOSE 8471
ENTRYPOINT ["python", "-m", "travellings_graph"]
