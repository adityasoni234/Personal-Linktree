# Deployment

## Before you start

You need: a host with Docker, a domain, DNS pointing at it, and TLS
certificates. Everything else the stack provides.

> **Decide your public URL first.** `PUBLIC_BASE_URL` is what every QR code
> encodes. Changing it after codes are printed invalidates all of them — the
> images keep working but point at an address that no longer resolves. Pick the
> final domain before anyone prints anything.

---

## 1. Configure

```bash
cp .env.example .env
```

Generate real secrets:

```bash
python3 - <<'PY'
import secrets
for name, length in [
    ("JWT_SECRET", 64), ("JWT_REFRESH_SECRET", 64),
    ("ANALYTICS_IP_PEPPER", 32), ("POSTGRES_PASSWORD", 32), ("REDIS_PASSWORD", 32),
]:
    print(f"{name}={secrets.token_urlsafe(length)}")
PY
```

Production values that must change from the defaults:

```env
ENVIRONMENT=production
DEBUG=false
LOG_JSON=true

COOKIE_SECURE=true
COOKIE_SAMESITE=lax
COOKIE_DOMAIN=.linkhub.ieeesou.org      # only if you use subdomains

CORS_ORIGINS=https://linkhub.ieeesou.org
FRONTEND_URL=https://linkhub.ieeesou.org
PUBLIC_BASE_URL=https://linkhub.ieeesou.org
VITE_API_BASE_URL=/api/v1

STORAGE_BACKEND=s3
STORAGE_BUCKET=ieeesou-linkhub-media
STORAGE_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
STORAGE_PUBLIC_BASE_URL=https://media.linkhub.ieeesou.org
```

`app/core/config.py` refuses to boot in production with weak or missing secrets,
`DEBUG=true`, `COOKIE_SECURE=false`, a wildcard or plaintext CORS origin, or an
`s3` backend without a bucket. That check is the last line of defence — treat a
boot failure as the system doing its job.

---

## 2. TLS

```bash
mkdir -p infra/nginx/certs
```

**Let's Encrypt:**

```bash
sudo certbot certonly --standalone -d linkhub.ieeesou.org
sudo cp /etc/letsencrypt/live/linkhub.ieeesou.org/fullchain.pem infra/nginx/certs/
sudo cp /etc/letsencrypt/live/linkhub.ieeesou.org/privkey.pem   infra/nginx/certs/
sudo chown $USER infra/nginx/certs/*.pem && chmod 600 infra/nginx/certs/privkey.pem
```

Add a renewal hook that copies the new files and reloads nginx:

```bash
# /etc/letsencrypt/renewal-hooks/deploy/linkhub.sh
cp /etc/letsencrypt/live/linkhub.ieeesou.org/{fullchain,privkey}.pem /srv/linkhub/infra/nginx/certs/
docker compose -f /srv/linkhub/docker-compose.prod.yml exec nginx nginx -s reload
```

If you terminate TLS at a CDN instead, keep the proxy configuration: the
application relies on `X-Forwarded-For` being **overwritten** by the last hop,
without which per-IP rate limits can be spoofed.

---

## 3. Launch

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
curl -sf https://linkhub.ieeesou.org/health && echo OK
curl -s  https://linkhub.ieeesou.org/ready
```

Migrations run from the container entrypoint, which waits for Postgres and Redis
first. To run them by hand:

```bash
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.prod.yml exec backend alembic current
```

---

## 4. First administrator

Either register through the UI — **the first account in an organization becomes
its administrator** — or bootstrap a platform super-administrator by setting
these before first boot:

```env
BOOTSTRAP_SUPERADMIN_EMAIL=tech@ieeesou.org
BOOTSTRAP_SUPERADMIN_PASSWORD=<a strong password>
```

Remove both from `.env` once the account exists. The bootstrap never overwrites
an existing account's password.

---

## 5. Verify

```bash
# Security headers
curl -sI https://linkhub.ieeesou.org/api/v1/groups | grep -iE \
  'strict-transport|content-security|x-frame|x-content-type|referrer-policy'

# Interactive docs must be gone
curl -s -o /dev/null -w '%{http_code}\n' https://linkhub.ieeesou.org/docs   # 404

# CORS must reject an unlisted origin
curl -sI -H 'Origin: https://evil.example' https://linkhub.ieeesou.org/api/v1/groups \
  | grep -i access-control-allow-origin                                      # no output

# Rate limiting must engage
for i in $(seq 1 8); do
  curl -s -o /dev/null -w '%{http_code} ' -X POST \
    https://linkhub.ieeesou.org/api/v1/auth/login \
    -H 'content-type: application/json' \
    -d '{"email":"nobody@example.com","password":"wrong-password-1"}'
done; echo                                                                   # ends in 429
```

Then, manually: create a group, publish it, **scan the printed QR with a real
phone**, and confirm the click redirect lands on the right destination.

---

## Operations

### Backups

```bash
# Nightly database dump
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "backup-$(date +%F).sql.gz"

# Restore
gunzip -c backup-2026-08-17.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

Back up media too (the bucket, or the `media_data` volume). Restore is only real
once you have tested it — do that before you need it.

### Monitoring

| Signal | Where |
|---|---|
| Liveness | `GET /health` |
| Readiness (DB + Redis) | `GET /ready` — 503 when degraded |
| Security events | `app.security` logger |
| Audit trail | `app.audit` logger and the `audit_logs` table |
| Slow requests | `X-Response-Time` header, `duration_ms` in logs |

Alert on: `/ready` failing, a spike in `login_lockout_applied`, any
`refresh_token_reuse_detected`, and `rate_limit_backend_unavailable`.

### Housekeeping

`auth_service.purge_expired_tokens()` deletes sessions and reset tokens more
than 30 days expired. Run it weekly:

```bash
docker compose -f docker-compose.prod.yml exec backend python -c "
import asyncio
from app.db.session import session_scope
from app.services.auth_service import purge_expired_tokens

async def main():
    async with session_scope() as db:
        print('removed', await purge_expired_tokens(db))

asyncio.run(main())
"
```

Consider a retention policy for `analytics_events` — the rows are small and
anonymised, but they grow without bound.

### Updating

```bash
git pull
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs -f backend
```

Take a database backup before any deploy that includes a migration.

---

## Scaling

The API is stateless; scale it horizontally. Session revocation, rate limiting
and analytics de-duplication all live in Redis, so replicas agree.

| Symptom | Action |
|---|---|
| CPU pinned during QR exports | More backend replicas; QR rendering is the CPU-heavy path and already runs off the event loop |
| Slow dashboards | Check `ix_analytics_*` are present; consider a daily rollup table |
| Media bandwidth | Move to `STORAGE_BACKEND=s3` behind a CDN |
| Redis memory | Raise `maxmemory`; the QR cache is the largest consumer and evicts safely |
| Database connections | Tune `DB_POOL_SIZE` × replicas to stay under Postgres `max_connections` |

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Boots then exits with "Insecure production configuration" | A production guard tripped. The message lists exactly which. |
| Sign-in works, reload signs you out | The API is not same-origin with the SPA, so the `SameSite` refresh cookie is not sent. Serve both through one origin. |
| `429` on every login | Redis is unreachable and auth endpoints fail closed — by design. Fix Redis. |
| QR downloads work, printed codes do not scan | Check contrast and logo size in the designer, and always test-scan before a print run. |
| SVG logo missing from PNG exports | `libcairo2` is absent from the image; the renderer degrades to skipping it. |
| Uploads fail with 413 | `MAX_UPLOAD_BYTES` or nginx `client_max_body_size` — raise both together. |
