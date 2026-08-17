# IEEE SOU Link Hub

A secure, organization-owned alternative to Linktree. Every chapter, committee
and event gets its own branded public page and a **dynamic QR code** — printed
once, re-pointable forever, because the code encodes the group page rather than
any individual link.

```
Organization → Users/Admins → Groups → Links → Public page → QR code → Analytics
```

```
IEEE SOU
├── Executive Committee   /g/executive-committee
├── Computer Society      /g/computer-society
├── WIE                   /g/wie
├── SPS                   /g/sps
├── SIGHT                 /g/sight
├── Events                /g/events
└── Workshops             /g/workshops
```

---

## Contents

- [What is in the box](#what-is-in-the-box)
- [Quick start](#quick-start)
- [Project layout](#project-layout)
- [Configuration](#configuration)
- [Development without Docker](#development-without-docker)
- [Testing](#testing)
- [API](#api)
- [Security model](#security-model)
- [Further documentation](#further-documentation)

---

## What is in the box

| Area | What it does |
|---|---|
| **Groups** | Create, edit, duplicate, archive, publish and reorder link pages. Unique, reserved-word-checked slugs. |
| **Links** | Per-group links with icons, descriptions, per-link styling, drag-and-drop *and* keyboard reordering, enable/disable, duplication. |
| **Public pages** | `/g/:slug`, mobile-first, themeable, with OpenGraph/Twitter metadata and a share sheet. |
| **QR designer** | Dot/eye/corner styles, gradients, logo embedding, frames and captions, six curated presets, PNG + SVG export, live contrast and scannability checks. |
| **Analytics** | QR scans, page views, per-link clicks, device/browser/referrer breakdowns — with no raw IP storage and no cross-site tracking. |
| **RBAC** | `SUPER_ADMIN` / `ADMIN` / `EDITOR` / `USER`, enforced on the server for every request. |
| **Audit log** | Append-only record of every security-sensitive action. |
| **Security** | Argon2id, rotating refresh tokens, CSRF double-submit, Redis rate limiting, brute-force lockout, sanitised uploads, strict CSP. |

---

## Quick start

**Requirements:** Docker and Docker Compose.

```bash
git clone <your-repo-url> ieee-link-hub && cd ieee-link-hub
cp .env.example .env
```

Generate real secrets and put them in `.env`:

```bash
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(64))"
python3 -c "import secrets; print('JWT_REFRESH_SECRET=' + secrets.token_urlsafe(64))"
python3 -c "import secrets; print('ANALYTICS_IP_PEPPER=' + secrets.token_urlsafe(32))"
```

Then bring the stack up:

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000/api/v1 |
| API docs | http://localhost:8000/docs (non-production only) |
| Health | http://localhost:8000/health |

Migrations run automatically on start, and the default organization
(`IEEE SOU`) is created on first boot. **The first account to register becomes
that organization's administrator** — so register yours before sharing the URL.

---

## Project layout

```
ieee-link-hub/
├── backend/
│   ├── app/
│   │   ├── api/            # routers (v1), dependencies, cookie handling
│   │   ├── core/           # config, logging, errors, redis, rate limiting
│   │   ├── db/             # engine, session, base, bootstrap
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response contracts
│   │   ├── services/       # business rules and authorization
│   │   ├── security/       # passwords, tokens, RBAC, CSRF, validators
│   │   ├── qr/             # QR geometry, renderers, presets, engine
│   │   ├── analytics/      # privacy-preserving ingestion
│   │   ├── storage/        # local + S3 backends
│   │   ├── middleware/     # security headers, request context, body limits
│   │   └── main.py
│   ├── migrations/         # Alembic
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/            # typed HTTP client and endpoints
│       ├── components/     # ui primitives, layout, builder, charts, public
│       ├── pages/          # routed screens
│       ├── hooks/  schemas/  stores/  lib/
│       └── App.tsx
├── infra/nginx/            # production reverse proxy
├── docs/                   # architecture, security, deployment
├── docker-compose.yml      # development stack
└── docker-compose.prod.yml # production stack
```

The layering rule: **routers parse and shape, services decide.** Every
authorization check and business rule lives in `app/services/`, so it is
reachable from tests and background jobs, not only from an HTTP request.

---

## Configuration

All configuration is environment-driven; see [`.env.example`](.env.example) for
the annotated list. The variables that matter most:

| Variable | Notes |
|---|---|
| `JWT_SECRET`, `JWT_REFRESH_SECRET` | Must differ, ≥32 characters. Production refuses to boot otherwise. |
| `ANALYTICS_IP_PEPPER` | Salt for visitor hashing. Rotating it resets unique-visitor continuity. |
| `CORS_ORIGINS` | Explicit comma-separated allowlist. `*` is rejected in production. |
| `PUBLIC_BASE_URL` | The origin QR codes encode. **Changing it invalidates every printed code.** |
| `COOKIE_SECURE` | Must be `true` in production. |
| `STORAGE_BACKEND` | `local` for a single node, `s3` for anything larger. |

`app/core/config.py` validates these on startup and fails loudly rather than
starting up insecurely.

> **Frontend note:** every `VITE_*` variable is compiled into the browser bundle
> and is public. Never put a secret there.

---

## Development without Docker

**Backend** (Python 3.12+, PostgreSQL 16, Redis 7):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Frontend** (Node 20+):

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies `/api` and `/media` to the backend, so the app is
same-origin with the API — which is what lets the `HttpOnly` refresh cookie
work. Point it elsewhere with `VITE_DEV_API_TARGET`.

---

## Testing

```bash
cd backend  && pytest                 # 255 tests, no external services needed
cd backend  && pytest -m security     # security-focused subset
cd frontend && npm test               # component and schema tests
cd frontend && npm run typecheck
```

The backend suite runs against SQLite and an in-memory Redis, so `pytest` works
on a clean checkout with no database running. Coverage includes the security
cases the brief calls for:

<details>
<summary>Security test coverage</summary>

| Case | Test |
|---|---|
| Unauthenticated API request | `test_authorization.py::test_protected_endpoints_require_authentication` |
| Unauthorized group modification | `test_authorization.py::test_member_cannot_edit_another_members_group` |
| Invalid / expired / `alg:none` JWT | `test_auth.py::test_malformed_tokens_are_rejected` |
| Refresh token replayed as access token | `test_auth.py::test_refresh_token_cannot_be_used_as_an_access_token` |
| Refresh token reuse | `test_auth.py::test_replaying_an_old_refresh_token_destroys_the_session` |
| CSRF missing / forged | `test_auth.py::test_refresh_requires_csrf_header` |
| Account enumeration | `test_auth.py::test_login_response_does_not_reveal_whether_account_exists` |
| Rate limit exceeded | `test_rate_limiting.py` (login, register, forgot-password) |
| Brute-force lockout ladder | `test_rate_limiting.py::test_lockout_duration_escalates` |
| Malicious URL schemes | `test_input_validation.py::test_dangerous_url_schemes_are_rejected` |
| XSS payloads | `test_input_validation.py::test_markup_and_invisible_characters_are_stripped` |
| SQL injection attempt | `test_input_validation.py::test_sql_injection_in_search_is_treated_as_text` |
| Path traversal | `test_uploads.py::test_local_storage_rejects_path_traversal` |
| Malicious SVG (9 payloads) | `test_uploads.py::test_malicious_svg_payloads_are_neutralised` |
| XXE / billion laughs | `test_uploads.py::test_xxe_entity_declaration_is_rejected` |
| Oversized upload / image bomb | `test_uploads.py::test_oversized_upload_is_rejected` |
| Polyglot and disguised files | `test_uploads.py::test_executable_disguised_as_png_is_rejected` |
| Role escalation | `test_authorization.py::test_admin_cannot_grant_super_admin` |
| Draft/archived page exposure | `test_public_pages.py::test_draft_group_is_not_publicly_visible` |
| Client-controlled analytics | `test_public_pages.py::test_client_cannot_choose_which_group_an_event_belongs_to` |
| QR target tampering | `test_qr.py::test_qr_always_encodes_the_group_page_never_a_client_supplied_url` |
| Unbounded pagination | `test_input_validation.py::test_pagination_limit_is_clamped` |

</details>

---

## API

Versioned under `/api/v1`. Interactive docs at `/docs` (disabled in production).

```
POST   /api/v1/auth/register           POST   /api/v1/auth/login
POST   /api/v1/auth/refresh            POST   /api/v1/auth/logout
GET    /api/v1/auth/me                 PATCH  /api/v1/auth/me
POST   /api/v1/auth/forgot-password    POST   /api/v1/auth/reset-password
POST   /api/v1/auth/change-password    GET    /api/v1/auth/sessions

GET    /api/v1/groups                  POST   /api/v1/groups
GET    /api/v1/groups/{id}             PATCH  /api/v1/groups/{id}
DELETE /api/v1/groups/{id}             POST   /api/v1/groups/{id}/publish
POST   /api/v1/groups/{id}/archive     POST   /api/v1/groups/{id}/duplicate
POST   /api/v1/groups/reorder

GET    /api/v1/groups/{id}/links       POST   /api/v1/groups/{id}/links
PATCH  /api/v1/links/{id}              DELETE /api/v1/links/{id}

GET    /api/v1/groups/{id}/qr          POST   /api/v1/groups/{id}/qr
POST   /api/v1/groups/{id}/qr/preview  GET    /api/v1/groups/{id}/qr.{png|svg}
GET    /api/v1/qr/presets

GET    /api/v1/groups/{id}/analytics   GET    /api/v1/analytics/overview
POST   /api/v1/media                   GET    /api/v1/admin/users
GET    /api/v1/admin/audit-logs        PATCH  /api/v1/admin/organization

GET    /api/v1/public/groups/{slug}                    (published groups only)
GET    /api/v1/public/groups/{slug}/links/{id}         (302 + click tracking)
GET    /api/v1/public/groups/{slug}/qr.{png|svg}
```

**Every response uses one envelope.**

```jsonc
// success
{ "success": true, "data": { } }

// paginated
{ "success": true, "data": [], "meta": { "page": 1, "limit": 20, "total": 42, "pages": 3 } }

// error
{ "success": false, "error": { "code": "RESOURCE_NOT_FOUND", "message": "Group not found" } }
```

Rate-limited responses carry `Retry-After`, `X-RateLimit-Limit` and
`X-RateLimit-Remaining`. Every response carries `X-Request-ID`, which also
appears in the error body and the logs.

---

## Security model

The full write-up is in [`docs/SECURITY.md`](docs/SECURITY.md). In brief:

- **Passwords** — Argon2id (64 MiB, 3 passes), policy-checked, transparently
  re-hashed when parameters change.
- **Sessions** — 15-minute access token in memory only; refresh token in an
  `HttpOnly`/`Secure`/`SameSite` cookie, rotated on every use, with reuse
  detection that revokes the whole family (and a short grace window so two tabs
  do not look like theft).
- **Authorization** — decided server-side on every request against the stored
  row. The frontend's route guards are UX, not a boundary.
- **Rate limiting** — Redis sliding window keyed by IP *and* by user *and* by
  endpoint; authentication endpoints fail **closed** if Redis is unreachable.
- **Uploads** — type determined from the bytes, rasters re-encoded (stripping
  EXIF and defusing polyglots), SVGs rebuilt from an allowlist, server-generated
  filenames, storage outside the application directory.
- **Analytics** — no raw IPs, no cross-site identifiers; visitor hashes are
  salted with a secret pepper *and* a daily rotating salt.
- **Headers** — CSP, HSTS, `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, COOP/CORP.

### The one invariant to remember

A group's QR code always encodes **that group's own public page**. It is derived
server-side from the slug and can never be set by a client. Change the links
behind a page as often as you like — every printed poster keeps working.

---

## Further documentation

| Document | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Data model, request lifecycle, QR pipeline, analytics design |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Threat model, controls, and what is deliberately out of scope |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Production checklist, TLS, backups, scaling, operations |

---

## Licence

MIT. Built for the IEEE Silver Oak University Student Branch.
