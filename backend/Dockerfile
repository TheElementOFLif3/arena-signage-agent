FROM python:3.12-slim

# System deps (za psycopg2 i sl.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Ne-root user
RUN useradd -m appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Aplikacija
COPY app ./app

# Make static folder readable (ispravan path!)
RUN chmod -R 755 /app/app/static || true

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]