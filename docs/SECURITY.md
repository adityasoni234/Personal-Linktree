# Security model

This document describes what the application defends against, how, and what is
deliberately out of scope. Controls are listed with the file that implements
them so a reviewer can go straight to the code.

---

## Threat model

The realistic adversaries for a student-branch link platform:

| Adversary | Goal | Primary controls |
|---|---|---|
| Credential stuffer | Reuse leaked passwords | Rate limiting, lockout ladder, Argon2id, no enumeration |
| Bored student | Deface another chapter's page | Server-side RBAC, ownership checks, audit log |
| XSS/upload attacker | Run script on the org's domain | Strict CSP, no HTML rendering, SVG sanitisation, re-encoded rasters |
| Phisher | Repoint a printed QR at a fake page | QR target derived server-side; URL scheme allowlist; no open redirect |
| Scraper | Harvest members or draft pages | Public projection excludes internals; drafts are indistinguishable from missing |
| Abuser | Inflate analytics or exhaust CPU | Server-derived events, de-duplication, bot filtering, render limits |

Out of scope, and why: **email verification** (accounts are added by an
administrator in practice, and the code path is present but not enforced),
**WAF/DDoS** (belongs at the CDN), **secret management** (use your platform's
secret store; the app only reads environment variables).

---

## Authentication

**Passwords** — `app/security/passwords.py`

- Argon2id, 64 MiB memory, 3 passes, 2 lanes, 16-byte salt.
- Policy: 10–128 characters, three of four character classes, no
  four-character repeats, not a well-known password, not derived from the user's
  own email or name.
- `check_needs_rehash` upgrades stored hashes transparently at next sign-in when
  parameters are raised.
- Unknown accounts still run a dummy verification, so response timing does not
  leak account existence.

**Tokens** — `app/security/tokens.py`

| | Access | Refresh |
|---|---|---|
| Lifetime | 15 minutes | 14 days (sliding, hard-capped at 28) |
| Transport | `Authorization: Bearer` | `HttpOnly` + `Secure` + `SameSite` cookie |
| Storage | Frontend memory only | Browser cookie jar; digest only in the database |
| Signing key | `JWT_SECRET` | `JWT_REFRESH_SECRET` (must differ) |

Both are type-tagged (`typ`) and the algorithm is pinned on decode, which
defeats `alg: none` and cross-family replay. Tokens carry `iss`/`aud` and
require `exp`, `iat`, `sub`, `jti`, `typ`.

**Rotation and reuse detection** — `app/services/auth_service.py`

Every refresh mints a new token and demotes the current digest to
`previous_token_hash`. Presenting a token that was already rotated away:

- **within 20 seconds** → treated as a benign race (two tabs, a retried
  request) and rotated normally;
- **after that** → treated as theft. The entire session family is revoked, an
  `TOKEN_REUSE_DETECTED` audit entry is written, and the user must sign in again.

**Revocation.** Access tokens are stateless, so logout also writes the session id
to a Redis revocation list with a TTL just longer than the access-token
lifetime. The auth dependency checks it on every request, falling back to the
database if Redis is unavailable — never failing open.

`users.tokens_valid_after` retires every token issued before a given instant, and
is bumped on password change, password reset, role change and forced sign-out.

---

## Authorization

`app/security/rbac.py` — a single permission matrix, checked server-side.

```
SUPER_ADMIN  everything, across all organizations
ADMIN        their organization: groups, members, roles, audit log
EDITOR       create and edit groups and links in their organization
USER         only the resources they own
```

Two layers:

1. **Route-level** `require_permission(...)` for coarse gates.
2. **Resource-level** `can_edit_group(...)` and friends in the service layer,
   evaluated against the **stored row** — never against an owner id supplied by
   the client.

Guarantees enforced by `assert_can_assign_role`:

- you cannot change your own role,
- you cannot grant a role above your own,
- you cannot modify anyone at or above your own rank,
- only a `SUPER_ADMIN` can mint another `SUPER_ADMIN`.

A role change bumps `tokens_valid_after`, so it takes effect immediately rather
than when the victim's token happens to expire.

**Not-found beats forbidden.** Reading a group you may not see returns `404`, not
`403` — a `403` would confirm the id exists.

The frontend's route guards (`components/RouteGuards.tsx`) decide what to
*render*. They are a user-experience control; bypassing them in devtools gains
an attacker nothing.

---

## Input validation

Everything is validated twice: once in the browser for fast feedback, once on
the server as the enforcement point.

**URLs** — `app/security/url_validation.py`

- Allowlist: `http`, `https`, plus `mailto` and `tel` as explicitly reviewed
  contact schemes.
- Rejected loudly: `javascript`, `data`, `vbscript`, `file`, `blob`, `about`,
  `chrome`, `jar`, `view-source`, `ftp` and others — so the attempt is visible
  in the logs rather than silently dropped.
- Control characters and backslashes are rejected before parsing, which defeats
  `java\nscript:` style smuggling.
- Embedded credentials (`https://user:pass@evil.example`) are rejected.
- Hostnames go through an IDNA round-trip; in production, private and loopback
  addresses are refused.

**Slugs** — `app/security/slug.py`. Lowercase, hyphen-separated, 3–48
characters, checked against a reserved list covering every current and plausible
future route (`admin`, `api`, `login`, `dashboard`, `qr`, `g`, …), and refused
if they look like a bare identifier.

**Text** — `app/security/sanitize.py`. No HTML is accepted anywhere, so markup is
stripped rather than filtered. Zero-width and bidirectional-override characters
are removed (they enable invisible "Trojan Source" style spoofing in names).

**Mass assignment.** Update schemas set `extra="forbid"`, so posting
`{"owner_id": "..."}` is a `422`, not a silent privilege change.

---

## Uploads

`app/security/image_validation.py` and `svg_sanitizer.py`

1. Size capped while streaming — before anything is buffered whole.
2. Type determined from **magic bytes**; the declared content type and the
   filename extension must agree with them but never override them.
3. Dimension and total-pixel ceilings guard against decompression bombs.
4. Rasters are **re-encoded to PNG**, which strips EXIF/GPS and destroys
   appended payloads (a valid PNG that is also a valid PHP file stops being one).
5. SVGs are parsed with a hardened parser (DTD, entities and external
   references all forbidden) and **rebuilt from an element/attribute allowlist**.
   Dropped: `<script>`, `<foreignObject>`, `<image>`, `<animate>`, `<style>`,
   every `on*` handler, any `href` that is not a same-document fragment, and any
   `url()` that is not `url(#id)`.
6. Filenames are server-generated; the user-supplied name is a display label
   only. Local storage re-resolves every path against its root.
7. Media lives outside the application directory, and nginx refuses to serve
   executable extensions from it.

---

## Rate limiting and brute force

`app/core/rate_limit.py`, `app/security/bruteforce.py`

A Redis sliding window implemented as one Lua script, so check-and-increment is
atomic across workers. A pipeline fallback covers Redis deployments without
scripting.

| Endpoint | Limit |
|---|---|
| Login | 5/min per IP **and** 10/15 min per account |
| Register | 5/hour per IP |
| Forgot password | 3/15 min per IP **and** 3/hour per account |
| API (general) | 100/min per user |
| Writes | 60/min per user |
| QR render | 30/min per user |
| Media upload | 20/5 min per user |
| Public page | 120/min per IP |

Keying by IP **and** by account is the point: rotating the email does not reset
the IP budget, and a botnet does not reset the account budget.

**Authentication endpoints fail closed.** If Redis is unreachable they return
`429` rather than proceeding unlimited — losing the limiter there would open the
door to unbounded credential stuffing. Everything else fails open with a
`SECURITY`-level log line.

On top of volume limiting, failed logins feed a lockout ladder (5 → 60s,
8 → 5 min, 12 → 30 min, 20 → 2 h) plus a progressive delay after three failures.
Identifiers are hashed before they reach Redis, so raw emails are never stored
there.

---

## Web-layer controls

**CSP.** API responses get `default-src 'none'; frame-ancestors 'none'; sandbox`
— they are JSON, and nothing should ever execute. Media gets a sandboxed policy
so an uploaded SVG cannot act in the origin. Docs get a narrow policy and are
disabled entirely in production.

Also set: HSTS (production only), `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`,
`Permissions-Policy` denying camera/microphone/geolocation/payment/usb and
opting out of Topics, COOP `same-origin`, CORP `same-site`, and `Cache-Control:
no-store` on API responses.

**CORS.** An explicit origin allowlist with credentials enabled. `*` is
impossible: credentialed CORS forbids it, and the config layer rejects it in
production outright — along with plaintext origins, `DEBUG=true`, weak secrets
and `COOKIE_SECURE=false`.

**CSRF.** Most endpoints authenticate with a bearer header, which browsers never
attach automatically. The two cookie-authenticated endpoints (`/auth/refresh`,
`/auth/logout`) use a signed double-submit token: a JS-readable `lh_csrf` cookie
echoed in `X-CSRF-Token`, carrying an HMAC so a sibling subdomain cannot mint one.

**Open redirects.** The click-tracking route redirects only to the stored,
already-validated link URL, looked up by id *within the group named in the path*
— a link id from another group returns `404`.

---

## Privacy

- Raw IP addresses are never persisted. `analytics_events.visitor_hash` and
  `audit_logs.ip_hash` are `sha256(pepper + daily-salt + ip)`.
- The daily salt means a visitor is countable within a day and uncorrelatable
  across days.
- Referrers are reduced to a bare domain; paths and query strings (which carry
  campaign and personal data) are discarded.
- User-agent strings are reduced to a device/browser/OS family. The truncated
  raw string is kept only as a session label so a user can recognise their own
  devices.
- No third-party scripts, pixels or fonts are loaded by the public page.

---

## Auditing and logging

`audit_logs` is append-only and records logins, failures, logouts, password
changes and resets, token-reuse detections, every group/link/QR/media mutation,
role changes, suspensions and organization settings changes — with actor,
resource, hashed IP and scrubbed metadata.

Logging is structured JSON in production and split by channel (`app`,
`app.security`, `app.audit`). A redaction filter strips `password`, `token`,
`secret`, `authorization`, `cookie` and similar keys at any nesting depth, so a
careless `extra={...}` cannot leak a credential.

---

## Deployment expectations

The application assumes it sits behind a reverse proxy that terminates TLS and
**overwrites** `X-Forwarded-For` (see `infra/nginx/proxy_headers.conf`). Without
that, a client could spoof the header and sidestep per-IP limits. Uvicorn is
started with `--forwarded-allow-ips` restricted to the proxy network.

Pre-flight checklist for production is in [`DEPLOYMENT.md`](DEPLOYMENT.md).

---

## Reporting a vulnerability

Email the IEEE SOU Student Branch technical team rather than opening a public
issue. Include the request id from the response body if you have one — it ties
directly to the server-side log entry.
