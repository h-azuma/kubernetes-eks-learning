FROM python:3.11.18-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY src ./src
RUN pip install --no-cache-dir -c requirements.lock .
COPY alembic.ini ./
COPY migrations ./migrations
RUN useradd --create-home --uid 10001 workboard
USER workboard
EXPOSE 8000
CMD ["uvicorn", "workboard.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test
USER root
RUN pip install --no-cache-dir -c requirements.lock '.[test]'
COPY tests ./tests
USER workboard
CMD ["pytest", "-q", "-p", "no:cacheprovider"]
