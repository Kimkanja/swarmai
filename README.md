# Swarm AI — Trading Software Licensing Platform

A full-stack Flask application for selling and licensing trading software
(EAs). Products, pricing, and access rules are all database-driven and
managed from an admin dashboard — nothing is hard-coded.

## What's included

- Public site: homepage, product catalog, product detail pages, how-it-works, FAQ, contact
- Auth: register, login, logout, forgot/reset password (secure hashing via Werkzeug, server-side sessions via Flask-Login)
- User dashboard: license list with status, referral link, profile management
- Referral / affiliate system: users get a unique referral code and link; a
  product can offer free access in exchange for completing an affiliate
  requirement, reviewed and approved by an admin
- License system: unique, cryptographically-random keys (`XXXX-XXXX-XXXX-XXXX`),
  per-product, per-user, with status (active/suspended/revoked), optional
  expiration, and activation-limit enforcement per account/terminal
- **License validation API** for the EA to call (`/api/license/validate`,
  `/api/license/deactivate`, `/api/license/status/<key>`) — HMAC-signed
  responses, rate-limited per key, generic failure messages (doesn't leak
  which keys exist), maintenance-mode support
- Admin dashboard (`/admin`, role-protected — never trusts a client-supplied
  role): manage users, products (incl. image upload), licenses, referral
  verifications, and platform settings
- Payment abstraction (`app/services/payment_service.py`): no payment
  provider is wired in since none was supplied in the brief. It currently
  falls back to a product's configured external `purchase_url`, or records
  a pending order and tells the user to contact support. Swap in a real
  provider by editing that one file.

## Product & pricing data

Two placeholder products are seeded (`flask seed-products`): **Vertex
Millionaire** and a placeholder **Second Product**. Both are created in
`draft` status with no price set (`price = NULL` → shows "Contact us") and
no invented content — fill in the real name, description, features, price,
and image for both from **Admin → Products**, then set status to `live` to
publish. The architecture supports any number of products; nothing is
hard-coded to "two".

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: set SECRET_KEY, LICENSE_HMAC_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD
# at minimum. Leave DATABASE_URL unset to use the default local SQLite db.

mkdir -p instance
export FLASK_APP=run.py      # Windows (PowerShell): $env:FLASK_APP="run.py"

flask db init                # only once, first time
flask db migrate -m "initial schema"
flask db upgrade

flask seed-admin              # creates the admin user from ADMIN_EMAIL/ADMIN_PASSWORD
flask seed-products           # creates the two placeholder products (draft status)

flask run
```

Visit `http://127.0.0.1:5000`. Log into `/admin` with the admin credentials
from `.env`, publish your two products with real content, and you're live.

## Running tests

```bash
pip install pytest
pytest
```

## Project structure

```
app/
  __init__.py        # application factory
  config.py           # env-driven configuration
  extensions.py       # SQLAlchemy, Migrate, Login, CSRF instances
  forms.py             # all WTForms
  utils.py             # admin_required decorator
  cli.py               # flask seed-admin / seed-products commands
  models/              # User, Product, License, LicenseBinding, ValidationLog,
                        # ReferralVerification, Order, SiteSetting
  routes/               # main, auth, dashboard, products, referral, admin
  api/license.py        # EA-facing license validation API
  services/              # license_service, referral_service, payment_service
  templates/              # base.html + public/auth/dashboard/admin/components/errors
  static/                  # css/js/images/uploads
migrations/                # Flask-Migrate/Alembic migration history
tests/test_smoke.py         # registration, admin auth, full license+API flow
```

## The EA integration contract

The EA calls `POST /api/license/validate` with:

```json
{ "key": "XXXX-XXXX-XXXX-XXXX", "account": "<broker account or terminal id>",
  "product": "VERTEX_MILLIONAIRE", "ea_version": "1.0", "nonce": "<random>" }
```

Response (always signed):

```json
{
  "valid": true,
  "result": "valid",
  "message": "License active.",
  "server_time": "2026-09-09T08:40:24.113492Z",
  "nonce": "...",
  "signature": "<hmac-sha256 hex>",
  "product": "VERTEX_MILLIONAIRE",
  "expires_at": null,
  "recheck_hours": 6,
  "grace_hours": 72
}
```

The signature is `HMAC-SHA256(LICENSE_HMAC_SECRET, "{key}|{account}|{valid}|{server_time}|{nonce}")`.
The EA should reconstruct this string and compare signatures, so a spoofed
local server or edited hosts file can't fake a "valid" response. On network
failure the EA should honor `grace_hours` from its last successful check
before shutting down, and treat `result: "maintenance"` as "not a failure."

No server secret is embedded in the EA — the license key itself is the
only credential it presents, matching how the reference implementation
you supplied (Supabase edge function) was designed.

## Deploying to production

1. **Server**: any Linux VM with Python 3.11+.
2. **Database**: switch to PostgreSQL by setting `DATABASE_URL` in the
   production `.env` (e.g. `postgresql://user:pass@host:5432/swarmai`) —
   SQLAlchemy/Alembic migrations work unchanged.
3. **WSGI**: run with Gunicorn:
   ```bash
   gunicorn -w 4 -b 127.0.0.1:8000 run:app
   ```
4. **Reverse proxy**: put Nginx in front for TLS termination and static
   file serving. Example server block:
   ```nginx
   server {
       listen 443 ssl;
       server_name yourdomain.com;

       ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

       location /static/ {
           alias /path/to/swarmai/app/static/;
       }

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
5. **HTTPS**: use Certbot/Let's Encrypt against the Nginx config above.
6. **Environment**: set `FLASK_ENV=production`, a strong random
   `SECRET_KEY` and `LICENSE_HMAC_SECRET` (e.g. `python -c "import secrets;
   print(secrets.token_hex(32))"`), and real `ADMIN_EMAIL`/`ADMIN_PASSWORD`
   before running `flask seed-admin`.
7. **Process management**: run Gunicorn under systemd or supervisord so it
   restarts on crash/reboot.
8. **Backups**: for SQLite, back up the `instance/swarmai.db` file on a
   schedule; for PostgreSQL, use `pg_dump` on a cron schedule.
9. **Migrations on deploy**: `flask db upgrade` after pulling new code,
   before restarting the app server.

## Extending

- **Add a third product**: Admin → Products → New Product. No code changes
  needed.
- **Connect a payment provider**: implement `start_checkout()` and
  `handle_webhook()` in `app/services/payment_service.py`; wire the webhook
  URL into a new route in `app/routes/products.py` that marks the `Order`
  paid and calls `issue_license()`.
- **License expiration / renewal**: the `License` model already has
  `expires_at`; set it when issuing a license (e.g. for subscription
  products) and the validation API already rejects expired keys.
- **Per-device limits**: already enforced via `License.max_activations` and
  `LicenseBinding` — set a value above 1 to allow multiple accounts per key.
