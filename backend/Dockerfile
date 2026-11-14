FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements.lock* ./
# requirements.lock holds exact pins when present; requirements.txt holds the ranges.
RUN if [ -f requirements.lock ]; then pip install -r requirements.lock; else pip install -r requirements.txt; fi

COPY . .

RUN DJANGO_SECRET_KEY=build DATABASE_URL=postgres://x:x@localhost/x python manage.py collectstatic --noinput

EXPOSE 8000

# Migrations run on release (section 12); workers are stateless.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py createcachetable && gunicorn config.asgi:application -k uvicorn_worker.UvicornWorker -b 0.0.0.0:8000 -w ${WEB_CONCURRENCY:-2} --timeout 620"]
