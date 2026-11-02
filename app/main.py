"""ServiceDesk API — clients → jobs → invoices, with a live outstanding balance.

Small-business backend demo: SQLite, API-key auth, money in integer cents,
validation at the edge, referential integrity enforced by the database.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Response

from .auth import require_api_key
from .db import connect, init_db, rows_to_dicts
from .schemas import (
    ClientIn,
    InvoiceIn,
    InvoiceStatusIn,
    JobIn,
    JobStatusIn,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ServiceDesk API",
    version="1.0.0",
    description="Clients → jobs → invoices. Demo build by Terrell Hall (Elitze).",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------- clients
@app.post("/clients", status_code=201, dependencies=[Depends(require_api_key)])
def create_client(payload: ClientIn) -> dict:
    with connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO clients (name, email) VALUES (?, ?)",
                (payload.name.strip(), payload.email),
            )
        except Exception:
            raise HTTPException(409, "a client with that email already exists")
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@app.get("/clients", dependencies=[Depends(require_api_key)])
def list_clients(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                 q: str | None = None) -> dict:
    sql = "SELECT * FROM clients"
    params: list = []
    if q:
        sql += " WHERE name LIKE ? OR email LIKE ?"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with connect() as conn:
        items = rows_to_dicts(conn.execute(sql, params).fetchall())
        total = conn.execute("SELECT COUNT(*) AS n FROM clients").fetchone()["n"]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.get("/clients/{client_id}", dependencies=[Depends(require_api_key)])
def get_client(client_id: int) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "client not found")
    return dict(row)


@app.delete("/clients/{client_id}", status_code=204, dependencies=[Depends(require_api_key)])
def delete_client(client_id: int) -> Response:
    with connect() as conn:
        row = conn.execute("SELECT id FROM clients WHERE id = ?", (client_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "client not found")
        try:
            conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        except Exception:
            raise HTTPException(409, "client still has jobs attached")
    return Response(status_code=204)


# ------------------------------------------------------------------- jobs
@app.post("/jobs", status_code=201, dependencies=[Depends(require_api_key)])
def create_job(payload: JobIn) -> dict:
    with connect() as conn:
        client = conn.execute("SELECT id FROM clients WHERE id = ?", (payload.client_id,)).fetchone()
        if client is None:
            raise HTTPException(404, "client not found")
        cur = conn.execute(
            "INSERT INTO jobs (client_id, title, price_cents) VALUES (?, ?, ?)",
            (payload.client_id, payload.title.strip(), payload.price_cents),
        )
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@app.get("/jobs", dependencies=[Depends(require_api_key)])
def list_jobs(client_id: int | None = None, status: str | None = Query(None, pattern="^(open|done)$"),
              limit: int = Query(20, ge=1, le=100)) -> dict:
    sql, params = "SELECT * FROM jobs WHERE 1=1", []
    if client_id:
        sql += " AND client_id = ?"
        params.append(client_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        return {"items": rows_to_dicts(conn.execute(sql, params).fetchall())}


@app.patch("/jobs/{job_id}", dependencies=[Depends(require_api_key)])
def update_job_status(job_id: int, payload: JobStatusIn) -> dict:
    with connect() as conn:
        cur = conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (payload.status, job_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "job not found")
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row)


# --------------------------------------------------------------- invoices
@app.post("/invoices", status_code=201, dependencies=[Depends(require_api_key)])
def create_invoice(payload: InvoiceIn) -> dict:
    with connect() as conn:
        job = conn.execute("SELECT id FROM jobs WHERE id = ?", (payload.job_id,)).fetchone()
        if job is None:
            raise HTTPException(404, "job not found")
        cur = conn.execute(
            "INSERT INTO invoices (job_id, amount_cents) VALUES (?, ?)",
            (payload.job_id, payload.amount_cents),
        )
        row = conn.execute("SELECT * FROM invoices WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@app.get("/invoices", dependencies=[Depends(require_api_key)])
def list_invoices(status: str | None = Query(None, pattern="^(draft|sent|paid)$")) -> dict:
    sql, params = "SELECT * FROM invoices", []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    with connect() as conn:
        return {"items": rows_to_dicts(conn.execute(sql + " ORDER BY id DESC", params).fetchall())}


@app.patch("/invoices/{invoice_id}", dependencies=[Depends(require_api_key)])
def set_invoice_status(invoice_id: int, payload: InvoiceStatusIn) -> dict:
    with connect() as conn:
        paid_at = "datetime('now')" if payload.status == "paid" else "NULL"
        cur = conn.execute(
            f"UPDATE invoices SET status = ?, paid_at = {paid_at} WHERE id = ?",
            (payload.status, invoice_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "invoice not found")
        row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    return dict(row)


# ---------------------------------------------------------------- summary
@app.get("/summary", dependencies=[Depends(require_api_key)])
def summary() -> dict:
    """The number a business owner actually cares about."""
    with connect() as conn:
        clients = conn.execute("SELECT COUNT(*) AS n FROM clients").fetchone()["n"]
        open_jobs = conn.execute("SELECT COUNT(*) AS n FROM jobs WHERE status = 'open'").fetchone()["n"]
        outstanding = conn.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) AS c FROM invoices WHERE status != 'paid'"
        ).fetchone()["c"]
        paid = conn.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) AS c FROM invoices WHERE status = 'paid'"
        ).fetchone()["c"]
    return {
        "clients": clients,
        "open_jobs": open_jobs,
        "outstanding_cents": outstanding,
        "paid_cents": paid,
        "currency": "CAD",
    }
