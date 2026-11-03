# ServiceDesk API — small-business backend demo

A working FastAPI backend for the exact job most small businesses describe:
**clients → jobs → invoices, with a live outstanding balance.**

Built as a portfolio sample by **Terrell Hall** at **Elitze Agentic Security** (Victoria, BC) — the same stack I use for
paid automation work. Runs in one container, no external services, no ORM magic.

```
POST   /clients                  create (email unique, validated)
GET    /clients?q=&limit=&offset= search + pagination
GET    /clients/{id}
DELETE /clients/{id}             refused (409) while jobs exist
POST   /jobs                     requires an existing client
GET    /jobs?client_id=&status=
PATCH  /jobs/{id}                open → done
POST   /invoices                 requires an existing job
GET    /invoices?status=draft|sent|paid
PATCH  /invoices/{id}            mark sent/paid (paid_at stamped)
GET    /summary                  clients, open jobs, outstanding and paid totals
GET    /health                   no auth
```

## Run it

```bash
pip install -r requirements.txt
export SERVICE_API_KEY=change-me          # PowerShell: $env:SERVICE_API_KEY="change-me"
uvicorn app.main:app --reload
```

- Interactive docs: <http://127.0.0.1:8000/docs>
- Every endpoint except `/health` requires the header `X-API-Key: change-me`

```bash
curl -s localhost:8000/clients -H "X-API-Key: change-me" | jq
```

## Docker

```bash
docker build -t servicedesk .
docker run -p 8000:8000 -e SERVICE_API_KEY=change-me servicedesk
```

## Tests

```bash
pytest -q
```

12 tests cover auth rejection, validation, duplicate emails, referential integrity
(can't delete a client that still has jobs), invoice lifecycle, and the summary math.

## Design decisions worth noting

- **Money as integer cents.** No floats in a billing path, ever.
- **Database-enforced integrity.** Foreign keys `ON DELETE RESTRICT` + CHECK constraints, so a bad
  write fails at the storage layer even if a future endpoint forgets to validate.
- **Validation at the edge.** Pydantic models reject negative prices and malformed emails before
  any SQL runs.
- **Config via environment.** `SERVICE_DB` and `SERVICE_API_KEY` — no secrets in source.
- **No ORM.** Three tables; SQL is legible and each query is one statement.

## Not in this demo (what a paid build adds)

- OAuth2/JWT + per-tenant roles instead of a single API key
- Stripe/Interac invoicing integration and PDF rendering
- Migrations (Alembic) and row-level audit log
- Rate limiting and structured request logging
- CI (lint + tests + container scan)

Those are the parts a real engagement scopes — this repo exists to show the baseline quality
before the first invoice.

---

**Terrell Hall** · Victoria, BC · terrell0780@gmail.com ·
[github.com/terrell0780](https://github.com/terrell0780) ·
[Service page](https://terrell0780.github.io/elitze-site/) · Payment: Interac e-Transfer (CAD)
