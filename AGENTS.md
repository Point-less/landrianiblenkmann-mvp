# Project Quick Reference

- **Stack**: Django 4.2 + Strawberry GraphQL (Relay pagination), Dramatiq workers, Postgres 16, RabbitMQ 3, all delivered via Docker Compose (`docker compose up -d`).
- **Code layout**:
  - `users/` holds the custom `User` model, GraphQL filter definitions (`filters.py`), query mixins (`schema.py`), and shared types (`types.py`).
  - `config/schema.py` aggregates app-level schemas; `config/graphql.py` exposes an authenticated, CSRF-exempt GraphQL view mapped in `config/urls.py`.
  - `core/urls.py` surfaces health and Dramatiq trigger endpoints; other apps can follow the same pattern for modular routing.
- **Runtime defaults**:
  - GraphQL lives at `/graphql/`, rendered by Strawberry’s GraphiQL UI and protected by Django login. Project bootstrap creates `admin/admin` for local access.
  - Live code reload is handled in containers via `watchmedo`, so edits to `source/` invalidate Gunicorn and Dramatiq automatically.
- **Bootstrap command**: `python manage.py bootstrap` runs migrations and ensures the default superuser (`admin/admin`). Re-run after tearing down volumes.
- **Services**: `web` (Uvicorn + Django), `dramatiq` worker, `postgres`, `rabbitmq`. Ports exposed: `8001` (web), `15672`/`5672` (RabbitMQ UI/broker).
- **Dev workflow**: modify code under `source/`, call Dockerised management commands with `docker compose exec web ...`, use the bootstrap command to reset state, and drive Dramatiq via the `/trigger-log/` endpoint if needed (`docker compose up dramatiq` keeps the worker running).
