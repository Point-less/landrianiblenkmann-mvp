FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk add --no-cache build-base postgresql-dev pkgconf linux-headers bash

COPY source/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY source/ /app/

RUN python manage.py collectstatic --noinput --link

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
