# Project Quick Reference

> [!IMPORTANT]
> **Documentation Consistency**: This file must be kept in sync with the actual project structure. Every time any modification is made to the project architecture (new apps, services, URL patterns, models, or configuration changes), this document MUST be updated to reflect those changes.
> **Execution Policy**: From the host, only `docker` (including `docker compose`) and `git` commands should be run. All other commands (tests, manage.py, tooling, scripts) must be executed inside the `frontend` container via `docker compose exec frontend ...`.
> **Engineering Stance**: We code for correct states, not silent fallbacks. Required domain data (like operation types) must be present; missing prerequisites should raise errors loudly rather than defaulting or masking issues.

## Stack & Infrastructure

- **Framework**: Django 4.2 with Strawberry GraphQL (Relay pagination)
- **Task Queue**: Dramatiq workers with RabbitMQ 3 broker
- **Databases**: PostgreSQL 16, Redis 7.4 (caching + Dramatiq results)
- **Deployment**: Docker Compose (`docker compose up -d`)
- **Optional**: Cloudflared tunnel (enable with `docker compose --profile tunnel up`)

## Services

| Service | Port(s) | Purpose |
|---------|---------|---------|
| `frontend` | 8005 | Uvicorn + Django application server |
| `dramatiq` | - | Background task worker |
| `postgres` | 5432 (internal) | PostgreSQL database |
| `rabbitmq` | 5672 (broker), 15672 (UI) | Message broker + management UI |
| `redis` | 6379 | Cache and Dramatiq result backend |
| `cloudflared` | - | Optional Cloudflare tunnel (profile: `tunnel`) |

## Application Structure

The project is organized into 8 Django apps under `source/`:

### `config/`
Project configuration and routing hub.
- **Settings**: Django configuration, middleware (`RequireLoginMiddleware`), environment variables
- **Schema** (`schema.py`): Aggregates GraphQL schemas from apps (users, opportunities)
- **GraphQL** (`graphql.py`): Authenticated, CSRF-exempt GraphQL view
- **URLs** (`urls.py`): Root URL configuration routing to admin, graphql, and app-level URLs

### `core/`
Shared domain models and dashboard views.
- **Models**: `Agent` (commission split optional, % stored as 0-1 fraction), `Contact` (email required, tax id/condition, full address), `Property` (full address), `Currency`, `ContactAgentRelationship`
  - Contacts capture first/last name, full address, CUIT/CUIL (`tax_id`), and tax condition (RI/Monotributo/Exento/Consumidor final); email is required.
  - Agents store a `commission_split` (0-1 fraction of commissions allocated to them).
  - Properties store `full_address` in addition to name/reference code.
- **URLs** (`urls.py`): Dashboard views, health checks, entity CRUD (agents, contacts, properties), transition history
- **Views** (`views.py`): Workflow dashboard, entity management forms, health/trigger endpoints
- **Services** (`services/`): Command services plus query services (`services/queries.py`) for dashboard/form data (agents, contacts, properties, intentions, Tokkobroker props, currencies)
- **Purpose**: Foundation entities used across the real estate workflow

### `integrations/`
External service integrations.
- **Models**: `TokkobrokerProperty` - registry for externally-sourced properties
- **TokkobrokerClient** (`tokkobroker.py`): HTTP client for Tokkobroker API integration
- **Tasks** (`tasks.py`): Dramatiq tasks for syncing property data
- **URLs** (`urls.py`): Integration-specific endpoints

### `intentions/`
Pre-contract intent tracking with FSM state management.
- **Models**:
  - `SaleProviderIntention`: Property owner's pre-contract engagement (states: assessing → valuated → converted/withdrawn) with `operation_type` (Sale/Rent)
  - `SaleSeekerIntention`: Buyer's pre-representation interest (states: qualifying → active → mandated → converted/abandoned) with `operation_type`
  - `SaleValuation`: Valuation records delivered to providers
- **Valuations**: capture valuation_date and required test/close values (max 12 digits); promotion forms prefill client test/close values.
- **Purpose**: Capture and qualify leads before formal contracts
- **FSM States**: Uses django-fsm for state transitions with validation rules
- **URLs** (`urls.py`): Intention management endpoints

### `opportunities/`
Sales pipeline management with FSM workflows.
- **Models**:
  - `ProviderOpportunity`: Property opportunities (states: validating → marketing → closed)
    - Required `tokkobroker_property`, contract expiration; optional contract start; stores valuation test/close values.
  - `SeekerOpportunity`: Buyer opportunities (states: matching → negotiating → closed/lost)
  - `Validation`: Document validation workflow (states: preparing → presented → accepted)
  - Supporting models: `ValidationDocument`, `ValidationDocumentType` (configurable per operation type), `Match`, `Operation`, `OperationType` (Sale/Rent)
- **Operations**: require currency, reserve amount/deadline, initial offered amount; reinforcement captures offered_amount, reinforcement_amount, declared_deed_value; reserve/offered stored separately.
- **Commission tracking**: Provider and seeker opportunities store negotiated gross commission as a 0-1 fraction (e.g., 0.05 = 5%), defaulting to 4% via `DEFAULT_GROSS_COMMISSION_PCT`; agent commission split now lives on the Agent model.
- **Tokkobroker linking**: Provider opportunities must have an associated Tokkobroker property; promotion enforces this.
- **Schema** (`schema.py`, `types.py`, `filters.py`): GraphQL queries, types, and filtering for opportunities
- **Purpose**: Manage active sales pipeline from contract to close
- **URLs** (`urls.py`): Opportunity and validation management endpoints
 - **Services** (`services/`): Business logic for opportunity lifecycle
  - **Query services** (`services/queries.py`): read-only service classes (e.g., `AvailableProviderOpportunitiesForOperationsQuery`, `AvailableSeekerOpportunitiesForOperationsQuery`) to centralize “available for operations” selection logic with optional actor-aware filtering.

### `reports/`
Operational finance reporting.
- **Services**: `services/operations.py` builds the closed-operations financial/tax report (per agent).
- **Templates**: `templates/workflow/sections/reports_operations.html` renders the “Financial & Tax Report” table.
- **Purpose**: Display per-agent financial results for closed operations (closing date, client data, addresses, deed value, commissions, splits, agent/agency revenue).

### `users/`
Authentication and user management with passwordless login.
- **Models**: Custom `User` model (AUTH_USER_MODEL)
- **Views** (`views.py`): Custom login view with password and passwordless options, magic link request handler, logout
- **URLs** (`urls.py`): Login (`/auth/login/`), request magic link (`/auth/request-magic-link/`), sesame login endpoint (`/auth/sesame/login/`), logout
- **Schema** (`schema.py`): `UsersQuery` mixin for GraphQL
- **Types** (`types.py`): Strawberry types for GraphQL
- **Filters** (`filters.py`): GraphQL filter definitions
- **Templates**: Dual-mode login page (password + passwordless tabs), magic link request page
- **Purpose**: Authentication with both password and magic link (passwordless) login options

### `utils/`
Shared utilities and mixins.
- **Mixins**: `TimeStampedMixin` (created_at/updated_at), `FSMLoggableMixin` (django-fsm-log integration)
- **Audit helpers**: `FSMStateTransition` now stores `actor` (user responsible for each FSM transition); context helpers in `utils/actors.py`
- **Middleware**: `ActorContextMiddleware` binds the authenticated user to the transition logging context
- **Purpose**: DRY helpers used across all apps

## Domain Workflow

The system models a real estate agency's sales workflow:

1. **Intentions**: Capture provider (seller) and seeker (buyer) interest
2. **Opportunities**: Convert qualified intentions into active pipeline opportunities
3. **Validations**: Verify provider opportunity documentation (deed, authorization, etc.)
4. **Operations**: Close deals and record final transactions

State transitions use **django-fsm** with **django-fsm-log** for audit trails.

## GraphQL API

- **Endpoint**: `/graphql/` (protected by Django login, rendered with GraphiQL UI)
- **Schema** (`config/schema.py`): Merges `UsersQuery` + `OpportunitiesQuery`
- **Pagination**: Relay-style pagination via Strawberry
- **Authentication**: Requires login; protected by `RequireLoginMiddleware`

## URL Routing

| Pattern | App | Purpose |
|---------|-----|---------|
| `/admin/` | Django Admin | Admin interface |
| `/graphql/` | config | GraphQL endpoint (GraphiQL UI) |
| `/`, `/dashboard/` | core | Workflow dashboard and entity management |
| `/health/`, `/trigger-log/` | core | Health check and Dramatiq trigger endpoints |
| `/agents/`, `/contacts/`, `/properties/` | core | Entity CRUD |
| `/transitions/...` | core | FSM transition history |
| `/auth/login/` | users | Dual-mode login (password + passwordless) |
| `/auth/request-magic-link/` | users | Request passwordless login link |
| `/auth/sesame/login/` | users | Sesame magic link login endpoint |
| `/auth/logout/` | users | Logout endpoint |
| _App-specific patterns_ | intentions, opportunities, integrations | Modular routing per app |

## Bootstrap & Development

- **Bootstrap**: `python manage.py bootstrap` runs migrations and creates default superuser (`admin/admin`)
  - Re-run after `docker compose down -v` to reset state
- **Live Reload**: `watchmedo` auto-restarts Gunicorn and Dramatiq on code changes in `source/`
- **Management Commands**: `docker compose exec frontend python manage.py <command>`
- **Dramatiq Worker**: `docker compose up dramatiq` keeps worker running; trigger via `/trigger-log/`
- **Cloudflared Tunnel**: `docker compose --profile tunnel up` to enable

## Configuration

Environment variables (see `config/settings.py`):
- **Database**: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- **Redis**: `REDIS_CACHE_URL`, `REDIS_RESULTS_URL`
- **Dramatiq**: `DRAMATIQ_BROKER_URL` (RabbitMQ)
- **Tokkobroker**: `TOKKO_BASE_URL`, `TOKKO_USERNAME`, `TOKKO_PASSWORD`, `TOKKO_OTP_TOKEN`, `TOKKO_TIMEOUT`
- **Django**: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `TZ`

**Authentication Configuration**:
- **AUTHENTICATION_BACKENDS**: Sesame token backend (for magic links) + Django ModelBackend (for password login)
- **SESAME_MAX_AGE**: 300 seconds (5 minutes) - token expiration time
- **SESAME_ONE_TIME**: True - tokens can only be used once
- **EMAIL_BACKEND**: Console backend for development (prints emails to console)
- **LOGIN_URL**: `/auth/login/` - custom dual-mode login page

## Key Technologies

- **django-fsm** + **django-fsm-log**: State machine workflows with audit logging
- **django-sesame**: Passwordless authentication via one-time magic links (5-minute expiration)
- **Strawberry GraphQL**: Type-safe GraphQL with Relay pagination
- **Dramatiq**: Background task processing
- **Redis**: Caching layer and Dramatiq result backend
- **RabbitMQ**: Message broker for Dramatiq
- **watchmedo**: Hot reload for development
