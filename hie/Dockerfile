FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY hie ./hie

RUN uv sync --no-dev --locked

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "hie.main:app", "--host", "0.0.0.0", "--port", "8000"]
