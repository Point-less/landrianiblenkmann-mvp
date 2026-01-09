# Project Quick Reference

> [!IMPORTANT]
> Operational ritual: after **every** user message, first run `cat AGENTS_CRITICAL.md` from the repo root before doing anything else (skip it and a kitten will die). Keep this document in sync with the actual project structure whenever architecture changes (apps, services, URLs, models, config).
> Run the test suite (`docker compose exec frontend python manage.py test`) after changes; fix failures when feasible or report blockers explicitly.
> Run linting with ruff before committing: `docker compose exec frontend ruff check`.
> From the host, only use `docker`/`docker compose` and `git`. All other commands (manage.py, tooling, scripts, tests) must run in the `frontend` container via `docker compose exec frontend ...`.
> We code for correct states, not silent fallbacks: required domain data must exist; missing prerequisites should raise loudly.
> Follow OOP contracts—functions expect correctly typed objects; interact through public interfaces without duck-typing guards.
> All services must be covered by tests; add or update service-layer tests alongside behavior changes.
> Service layer coverage target: 100%—add tests until services are fully covered.

## Stack & Infrastructure

- **Framework**: Django 4.2 with Strawberry GraphQL (Relay pagination)
- **Task Queue**: Dramatiq workers with RabbitMQ 3 broker
- **Databases**: PostgreSQL 16, Redis 7.4 (caching + Dramatiq results)
- **Deployment**: Docker Compose (`docker compose up -d`)
- **Optional**: Cloudflared tunnel (`docker compose --profile tunnel up`)

## Services & Runtime

| Service | Port(s) | Purpose |
|---------|---------|---------|
| `frontend` | 8005 | Uvicorn + Django application server |
| `dramatiq` | - | Background task worker |
| `postgres` | 5432 (internal) | PostgreSQL database |
| `rabbitmq` | 5672 (broker), 15672 (UI) | Message broker + management UI |
| `redis` | 6379 | Cache and Dramatiq result backend |
| `cloudflared` | - | Optional Cloudflare tunnel (profile: `tunnel`) |

- `./source` is bind-mounted into the app containers; edits on host reflect immediately.
- Prefer hot reload: `frontend`/`dramatiq` use `watchmedo` autoreload. Rebuild images only when Dockerfiles or deps change.
- Logs: `docker compose logs frontend|dramatiq` to spot runtime/syntax issues.
- Install ad-hoc tools (e.g., `ripgrep`) inside containers if needed.

## Application Structure (under `source/`, 8 Django apps)

### `config/`
- Settings, middleware (`RequireLoginMiddleware`), env vars.
- GraphQL: `schema.py` aggregates app schemas; `graphql.py` authenticated CSRF-exempt view.
- URLs: root routing to admin, GraphQL, and app URLs.

### `core/`
- Models: `Agent` (commission_split fraction), `Contact` (email required, tax id/condition, full address), `Property` (full address), `Currency`, `ContactAgentRelationship`.
- URLs: dashboard views, health checks, CRUD for agents/contacts/properties, transition history.
- Views: workflow dashboard, entity management forms, health/trigger endpoints.
- Services: command services and queries (`services/queries.py`) for agents, contacts, properties, intentions, valuations, Tokkobroker props, currencies.
- Purpose: foundational entities across workflow.

### `integrations/`
- Model: `TokkobrokerProperty`.
- Client: `tokkobroker.py` for Tokkobroker API.
- Tasks: Dramatiq sync tasks.
- URLs: integration endpoints.

### `intentions/`
- Models: `ProviderIntention` (assessing → valuated → converted/withdrawn) and `SeekerIntention` (qualifying → active → mandated → converted/abandoned) with configurable `operation_type`; `Valuation`.
- Valuations capture valuation_date and required test/close values (max 12 digits); promotion forms prefill client test/close values.
- FSM via django-fsm; URLs for intention management.

### `opportunities/`
- Models: `ProviderOpportunity` (validating → marketing → closed; requires `tokkobroker_property`, contract expiration; stores valuation test/close), `SeekerOpportunity` (matching → negotiating → closed/lost), `Validation` (preparing → presented → accepted), `ValidationDocument`, `ValidationDocumentType` (per operation type), `Match`, `Operation`, `OperationType` (Sale/Rent).
- Operations require currency, reserve amount/deadline, initial offered amount; reinforcement captures offered_amount, reinforcement_amount, declared_deed_value; reserve/offered stored separately.
- Commission: gross commission stored as 0-1 fraction (default 4% via `DEFAULT_GROSS_COMMISSION_PCT`); agent split lives on `Agent`.
- Tokkobroker link required for provider opportunities; promotion enforces it.
- Schema (`schema.py`, `types.py`, `filters.py`): GraphQL queries, types, filtering.
- Validations: required docs must be reviewed. Extra uploads allowed only as custom docs while in `preparing`/`presented`; auto-accepted and listed with filenames/observations. Optional typed uploads disallowed.
- Services: lifecycle business logic; queries (`services/queries.py`) provide “available for operations” selections with optional actor-aware filtering.

### `reports/`
- Service `services/operations.py` builds closed-operations financial/tax report (per agent).
- Template `templates/workflow/sections/reports_operations.html` renders “Financial & Tax Report”.

### `users/`
- Custom `User` model (case-insensitive unique email).
- Views: password + passwordless login, magic link request, logout.
- URLs: `/auth/login/`, `/auth/request-magic-link/`, `/auth/sesame/login/`, `/auth/logout/`.
- GraphQL: `schema.py` (`UsersQuery`), `types.py`, `filters.py`.
- Templates: dual-mode login page; magic link request.

### `authorization` (in `users` + `utils`)
- Models (`users.models`): `Role`, `Permission`, `RolePermission`, `RoleMembership` (one-per-role per profile such as `core.Agent`), `ObjectGrant` (optional per-object allow/deny).
- Helpers (`utils/authorization.py`): `Action` constants, `check`, `filter_queryset`, `get_role_profile`, `explain`; superusers bypass.
- Template tag (`core/templatetags/authorization_tags.py`): `{% can "action.code" obj %}`.
- Seed command: `docker compose exec frontend python manage.py seed_permissions` seeds canonical roles/permissions (admin/manager all; agent operational only; viewer reports/integration dashboards view).

### `utils/`
- Mixins: `TimeStampedMixin`, `FSMLoggableMixin`.
- Audit: `FSMStateTransition` stores `actor`; helpers in `utils/actors.py`.
- Middleware: `ActorContextMiddleware` binds authenticated user to transition logging context.

## Domain Workflow

1. Intentions: capture provider/seeker interest.
2. Valuations: deliver/review provider property valuations before promotion.
3. Opportunities: convert qualified intentions into pipeline opportunities.
4. Validations: verify provider opportunity documentation.
5. Operations: close deals and record transactions.

State transitions use **django-fsm** with **django-fsm-log** for audit trails.

## GraphQL API

- Endpoint: `/graphql/` (login required; GraphiQL UI).
- Schema (`config/schema.py`): merges `UsersQuery` + `OpportunitiesQuery`.
- Pagination: Relay-style via Strawberry.
- Authentication: protected by `RequireLoginMiddleware`.

## URL Routing

| Pattern | App | Purpose |
|---------|-----|---------|
| `/admin/` | Django Admin | Admin interface |
| `/graphql/` | config | GraphQL endpoint |
| `/`, `/dashboard/` | core | Workflow dashboard & entity management |
| `/dashboard/provider-valuations/` | core | Provider valuations section |
| `/health/`, `/trigger-log/` | core | Health check & Dramatiq trigger |
| `/agents/`, `/contacts/`, `/properties/` | core | Entity CRUD |
| `/transitions/...` | core | FSM transition history |
| `/auth/login/` | users | Dual-mode login |
| `/auth/request-magic-link/` | users | Request passwordless login link |
| `/auth/sesame/login/` | users | Sesame magic link endpoint |
| `/auth/logout/` | users | Logout |
| _App-specific patterns_ | intentions, opportunities, integrations | Modular routing per app |

## Bootstrap & Development

- Bootstrap: `python manage.py bootstrap` (inside frontend) runs migrations and creates/updates superuser; set `BOOTSTRAP_ADMIN_PASSWORD` (and optionally username/email). Re-run after `docker compose down -v` to reset state.
- Live reload: `watchmedo` auto-restarts Gunicorn/Dramatiq on code changes in `source/`.
- Management commands: `docker compose exec frontend python manage.py <command>`.
- Migrations: never handcraft; run `docker compose exec frontend python manage.py makemigrations`.
- Dramatiq worker: `docker compose up dramatiq`; trigger via `/trigger-log/`.
- Cloudflared tunnel: `docker compose --profile tunnel up`.

## Configuration

Environment variables (see `config/settings.py`):
- Database: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- Redis: `REDIS_CACHE_URL`, `REDIS_RESULTS_URL`
- Dramatiq: `DRAMATIQ_BROKER_URL` (RabbitMQ)
- Tokkobroker: `TOKKO_BASE_URL`, `TOKKO_USERNAME`, `TOKKO_PASSWORD`, `TOKKO_OTP_TOKEN`, `TOKKO_TIMEOUT`
- Tokkobroker sync toggle: `TOKKO_SYNC_ENABLED` (default `true`)
- Django: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `TZ`

Authentication:
- `AUTHENTICATION_BACKENDS`: Sesame + ModelBackend
- `SESAME_MAX_AGE`: 300 seconds; `SESAME_ONE_TIME`: True
- `EMAIL_BACKEND`: console for dev
- `LOGIN_URL`: `/auth/login/`

## Repository Working Agreements

- Prefer smallest surface-area change; follow existing patterns.
- Make assumptions explicit; don’t proceed on guesses.
- Don’t edit existing migrations unless explicitly ordered; generate via `makemigrations`.
- Do not commit unless explicitly asked; one approval per commit.
- If unsure a change is fully working, pause and ask.

## Delivery Discipline

- Put real effort into making things work before asking for help.
- Run relevant commands/tests inside containers before declaring done.
- Report failing tests with details and blockers if unresolved.

## Reload & Rebuild Etiquette

- With bind mounts, rely on hot reload; avoid container rebuilds unless images/deps change.

## Coding Expectations

- Assume callers honor signatures; avoid redundant defensive checks.
- Prefer clear exceptions over silent fallbacks; require explicit inputs.
- Follow established OOP/polymorphism; avoid attribute-existence guards when contracts guarantee them.

## Planning Files

- Planning rules live in `AGENTS_PLANNING.md`. Only open it when the user explicitly asks for a plan (“plan”, “design”, “roadmap”, etc.). If the user wants direct implementation, draft a minimal plan in chat but keep `AGENTS_PLANNING.md` closed.
