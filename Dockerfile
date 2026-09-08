FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .

COPY src ./src
COPY configs ./configs
COPY models ./models
COPY sql ./sql

RUN pip install --no-cache-dir .

ENV RESTAURANT_RISK_PROJECT_ROOT=/app

RUN useradd --create-home --shell /usr/sbin/nologin appuser

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "restaurant_risk.api.app:app", "--host", "0.0.0.0", "--port", "8000"]