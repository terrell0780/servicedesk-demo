"""End-to-end API tests (pytest). Each test gets a fresh SQLite file."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

KEY = {"X-API-Key": "test-key"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SERVICE_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("SERVICE_API_KEY", "test-key")
    with TestClient(app) as c:
        yield c


def make_client(c, name="Acme Ltd", email="ops@acme.test"):
    r = c.post("/clients", json={"name": name, "email": email}, headers=KEY)
    assert r.status_code == 201, r.text
    return r.json()


def make_job(c, client_id, price=50000):
    r = c.post("/jobs", json={"client_id": client_id, "title": "Automate reporting",
                              "price_cents": price}, headers=KEY)
    assert r.status_code == 201, r.text
    return r.json()


def test_health_needs_no_auth(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_endpoints_require_api_key(client):
    assert client.get("/clients").status_code == 401
    assert client.get("/clients", headers={"X-API-Key": "wrong"}).status_code == 401


def test_create_and_fetch_client(client):
    created = make_client(client)
    assert created["email"] == "ops@acme.test"
    got = client.get(f"/clients/{created['id']}", headers=KEY).json()
    assert got["name"] == "Acme Ltd"


def test_duplicate_email_conflict(client):
    make_client(client)
    r = client.post("/clients", json={"name": "Acme 2", "email": "ops@acme.test"}, headers=KEY)
    assert r.status_code == 409


def test_invalid_email_rejected(client):
    r = client.post("/clients", json={"name": "Nope", "email": "not-an-email"}, headers=KEY)
    assert r.status_code == 422


def test_search_and_pagination(client):
    for i in range(3):
        make_client(client, name=f"Client {i}", email=f"c{i}@acme.test")
    r = client.get("/clients?q=Client 1", headers=KEY).json()
    assert r["total"] == 3 and len(r["items"]) == 1


def test_job_requires_existing_client(client):
    r = client.post("/jobs", json={"client_id": 999, "title": "x", "price_cents": 100}, headers=KEY)
    assert r.status_code == 404


def test_job_status_transition(client):
    c = make_client(client)
    job = make_job(client, c["id"])
    r = client.patch(f"/jobs/{job['id']}", json={"status": "done"}, headers=KEY)
    assert r.json()["status"] == "done"


def test_negative_price_rejected(client):
    c = make_client(client)
    r = client.post("/jobs", json={"client_id": c["id"], "title": "bad", "price_cents": -5}, headers=KEY)
    assert r.status_code == 422


def test_cannot_delete_client_with_jobs(client):
    c = make_client(client)
    make_job(client, c["id"])
    assert client.delete(f"/clients/{c['id']}", headers=KEY).status_code == 409


def test_invoice_lifecycle_and_summary_math(client):
    c = make_client(client)
    job = make_job(client, c["id"], price=125000)
    inv = client.post("/invoices", json={"job_id": job["id"], "amount_cents": 125000}, headers=KEY).json()

    s = client.get("/summary", headers=KEY).json()
    assert s["clients"] == 1
    assert s["open_jobs"] == 1
    assert s["outstanding_cents"] == 125000
    assert s["paid_cents"] == 0

    paid = client.patch(f"/invoices/{inv['id']}", json={"status": "paid"}, headers=KEY).json()
    assert paid["status"] == "paid" and paid["paid_at"]

    s2 = client.get("/summary", headers=KEY).json()
    assert s2["outstanding_cents"] == 0
    assert s2["paid_cents"] == 125000


def test_invoice_for_missing_job_404(client):
    r = client.post("/invoices", json={"job_id": 12345, "amount_cents": 100}, headers=KEY)
    assert r.status_code == 404
