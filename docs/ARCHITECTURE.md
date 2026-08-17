# Architecture

## System shape

```
                    ┌──────────────────────────────┐
   browser  ───────▶│  nginx (TLS, edge limits)    │
                    └──────────┬───────────┬───────┘
                               │           │
                   /api/*      │           │  everything else
                               ▼           ▼
                    ┌──────────────┐  ┌──────────────┐
                    │   FastAPI    │  │  built SPA   │
                    │  (uvicorn)   │  │   (static)   │
                    └───┬──────┬───┘  └──────────────┘
                        │      │
              ┌─────────▼─┐  ┌─▼──────────┐   ┌──────────────┐
              │ PostgreSQL│  │   Redis    │   │ object store │
              └───────────┘  └────────────┘   └──────────────┘
```

The SPA and the API are served from **one origin**. That is not incidental: the
refresh token is a `SameSite` cookie, and a cross-origin API would stop the
browser from sending it. The Vite dev server proxies `/api` for the same reason.

Redis is not a nice-to-have. It holds rate-limit windows, the session revocation
list, analytics de-duplication keys and the QR asset cache. The application
degrades predictably without it — authentication endpoints fail *closed*,
everything else fails *open* with a `SECURITY`-level log line.

---

## Data model

```
Organization ─┬── Membership ──── User ──┬── UserSession
              │                          └── PasswordResetToken
              ├── Group ─┬── Link
              │          └── QRConfiguration
              ├── Media
              ├── AnalyticsEvent
              └── AuditLog
```

| Table | Purpose | Notes |
|---|---|---|
| `organizations` | Tenant root | Slug-addressed; settings blob holds registration policy and quotas |
| `users` | Accounts | `system_role` is platform-wide; `tokens_valid_after` retires tokens en masse |
| `memberships` | User ↔ organization with a role | Unique per pair |
| `groups` | A public link page | Globally unique slug (it *is* the public URL) |
| `links` | Ordered links in a group | URL re-validated on every write |
| `qr_configurations` | QR design, one per group | Configuration only — images are rendered on demand |
| `media` | Uploaded assets | `storage_key` server-generated; original filename kept as a label only |
| `analytics_events` | Interactions | No raw IP; `visitor_hash` re-salts daily |
| `user_sessions` | Refresh-token families | Stores digests, never raw tokens |
| `audit_logs` | Append-only security trail | Metadata scrubbed before write |

**Design choices worth calling out:**

- **UUID primary keys everywhere.** Sequential ids would let anyone enumerate
  how many groups exist, and would make an id guessable in a URL.
- **Portable column types.** `Uuid` and `JSON` rather than Postgres-only
  `UUID`/`JSONB`, and non-native enums (VARCHAR + CHECK). This is what lets the
  whole test suite run on SQLite with no services — and it makes adding an enum
  member a data migration instead of an `ALTER TYPE` dance.
- **Composite indexes shaped like the queries.** `ix_groups_public_lookup`
  covers `(slug, is_published, is_archived)`, which is exactly the public page
  lookup; `ix_analytics_group_type_time` covers the reporting aggregates.
- **`ON DELETE` rules are explicit.** Deleting a group cascades to its links,
  QR configuration and events; deleting a user sets `groups.owner_id` to NULL
  rather than destroying the organization's pages.

---

## Request lifecycle

```
RequestContextMiddleware   assigns X-Request-ID, binds log context, times it
   └─ SecurityHeadersMiddleware   CSP, HSTS, nosniff, frame-options …
        └─ CORSMiddleware         explicit origin allowlist
             └─ BodySizeLimitMiddleware   rejects oversized bodies pre-routing
                  └─ route
                       ├─ rate_limit(...)      Redis sliding window
                       ├─ get_auth_context     decode token → re-read user → Principal
                       ├─ schema validation    Pydantic
                       └─ service layer        authorization + business rules
```

The `Principal` is rebuilt from the database on every request. The role inside
the access token is advisory only — a demotion takes effect on the very next
call rather than when the token expires.

### Errors

Every error path converges on one envelope through
`app/core/errors.py`. Handlers exist for `AppError`, `RequestValidationError`,
`HTTPException`, `SQLAlchemyError` and bare `Exception`. Database and unhandled
errors are logged in full and returned as a generic message — SQL text, file
paths and stack traces never cross the boundary.

---

## The QR pipeline

```
group.slug
   └─▶ target_url = {PUBLIC_BASE_URL}/g/{slug}?src=qr     ← server-derived, always
          └─▶ build_matrix(data, error_correction)         qrcode library
                 └─▶ build_geometry(spec)                  shapes, not pixels
                        ├─▶ render_svg()                   paths + gradients
                        └─▶ render_png()                   masks → composite → downscale
                               └─▶ Redis cache (keyed by a digest of the spec)
```

Both renderers consume the **same geometry**, so a design is identical in a
vector download and a raster export. Shapes are emitted as a small vocabulary
(`RoundedRect` with per-corner radii, `Circle`, `Polygon`, and a `Ring` for
finder outlines) that each renderer knows how to draw.

The PNG renderer rasterises into single-channel masks at a supersampled
resolution, composites a solid colour or gradient through them, then downscales
— which gives clean antialiased edges without a vector rasteriser. The working
resolution is capped so a large `size` request cannot exhaust memory.

**Why the configuration is stored but the image is not:** a group's design
changes often and its QR target never does. Persisting images would mean
invalidating and garbage-collecting assets on every edit; persisting the
*configuration* and caching renders in Redis makes a design change free and a
repeat download a single cache read.

### Scannability

`scannability_report()` returns advisory warnings; `qr_service._assert_scannable()`
hard-refuses a save that provably cannot scan. Both check:

- foreground/background contrast (≥ 3:1) and both gradient stops,
- **finder-pattern contrast** — a scanner locates a code by its three corner
  markers before reading any data, so a low-contrast eye breaks decoding even
  when the modules are fine,
- logo coverage against the error-correction budget (a logo forces level H),
- quiet-zone width.

---

## Analytics

The trust boundary is the point of the design: **the client can say that
something happened, never what.**

| Field | Source |
|---|---|
| group / link | the URL path |
| timestamp | the server clock |
| device, browser, OS | the `User-Agent` we received, reduced to a family |
| referrer | reduced to a bare domain — the path and query are discarded |
| country | a CDN-provided header, if one exists; never a GeoIP lookup |
| visitor | `sha256(pepper + daily-salt + ip)` |

Bots are classified and dropped. Repeat events from the same visitor are
de-duplicated in Redis with `SET NX` — atomic, so a burst of reloads cannot
inflate a count. Writes happen in a background task so a visitor never waits on
an analytics `INSERT`; the request context is snapshotted *before* the task is
scheduled, because the `Request` object does not outlive the response.

The visitor hash re-salts daily. That is deliberate: it supports unique-visitor
counts within a day and makes cross-day correlation impossible, which is the
trade the brief asks for.

---

## Frontend

```
main.tsx → App.tsx (routes, ErrorBoundary, Toaster)
   ├── public routes        eager: Landing, Login, PublicGroup
   └── everything else      lazy: dashboard, builder, admin
```

A visitor scanning a QR code downloads the public page and nothing else — the
dashboard is code-split behind the sign-in wall.

**State.** Zustand holds two stores: auth (access token in memory, never
persisted) and toasts. Server data uses a small `useQuery`/`useMutation` pair
rather than a full query cache; the app has no cross-screen cache-invalidation
requirements that would justify the dependency.

**The builder and the public page share one renderer.** `PublicPageView` is used
by both `/g/:slug` and the live preview, so what an author sees while editing is
literally the component visitors get — there is no second implementation to
drift.

**Charts** are hand-rolled inline SVG. The three-series palette is validated for
colourblind separation, and identity is carried by a legend and direct labels as
well as colour. Every chart offers a table view.
