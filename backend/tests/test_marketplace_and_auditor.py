"""Tasks 6/7: auditor decisions, credit issuance and marketplace guards."""
import threading
import uuid

import pytest

from app.database import SessionLocal
from app.models.credit import Credit
from app.models.verification import Verification
from conftest import TEST_NDVI, login, make_scored_plantation, plantation_payload, register


@pytest.fixture
def actors(client):
    farmer, _ = register(client, "FARMER", "Synthetic Farmer")
    buyer, _ = register(client, "BUYER", "Synthetic Buyer")
    auditor, _ = register(client, "AUDITOR", "Synthetic Auditor")
    return farmer, buyer, auditor


def _approved_credit(client, farmer, computed_ndvi_fixture=None):
    p = make_scored_plantation(client, farmer)
    v = client.post(f"/api/plantations/{p['id']}/verify", headers=farmer).json()
    assert v["decision"] == "APPROVED", v["decision_reasons"]
    credits = client.get("/api/marketplace/my-credits", headers=farmer).json()
    credit = next(c for c in credits if c["plantation_id"] == p["id"])
    return p, v, credit


def listed_ids(client):
    return {c["id"] for c in client.get("/api/marketplace/credits").json()}


def test_auto_approval_issues_listed_credit_with_honest_chain_status(client, actors, computed_ndvi):
    farmer, _, _ = actors
    p, v, credit = _approved_credit(client, farmer)
    assert credit["status"] == "AVAILABLE" and credit["is_listed"] is True
    assert credit["carbon_quantity_tco2e"] == pytest.approx(450 * 0.05, abs=0.1)
    assert credit["verification_id"] == v["id"] and credit["verification_decision"] == "APPROVED"
    # Blockchain is disabled in tests → must be NOT_RECORDED with no invented hash
    assert credit["blockchain_status"] == "NOT_RECORDED" and credit["blockchain_tx_hash"] is None
    assert credit["id"] in listed_ids(client)
    rec = client.get(f"/api/marketplace/credits/{credit['id']}/blockchain-record").json()
    assert rec["on_chain"] is False and rec["source"] == "DATABASE_ONLY" and rec["owner_address"] is None
    # Idempotent issuance
    again = client.post(f"/api/plantations/{p['id']}/generate-credits", headers=farmer, json={})
    assert again.status_code == 201 and again.json()["id"] == credit["id"]
    # Evidence and re-verification are locked once credits exist
    assert client.put(f"/api/plantations/{p['id']}/evidence", headers=farmer, json={"soil_soc_pct": 1.0}).status_code == 409
    assert client.post(f"/api/plantations/{p['id']}/verify", headers=farmer).status_code == 409


def test_pending_review_rejected_never_listed(client, actors):
    farmer, _, auditor = actors
    pending = client.post("/api/plantations", headers=farmer, json=plantation_payload()).json()
    client.post(f"/api/plantations/{pending['id']}/verify", headers=farmer)
    review = make_scored_plantation(client, farmer, **TEST_NDVI)
    rv = client.post(f"/api/plantations/{review['id']}/verify", headers=farmer).json()
    assert rv["decision"] == "REVIEW"
    for pid in (pending["id"], review["id"]):
        r = client.post(f"/api/plantations/{pid}/generate-credits", headers=farmer, json={})
        assert r.status_code == 409
    all_credits = client.get("/api/marketplace/credits", params={"status_filter": "ALL"}).json()
    assert not any(c["plantation_id"] in (pending["id"], review["id"]) for c in all_credits)

    # Auditor rejects the review case → still no credit
    r = client.post(f"/api/admin/verifications/{rv['id']}/decision", headers=auditor, json={"decision": "REJECTED", "notes": "Photo does not match boundary"})
    assert r.status_code == 200 and r.json()["decision"] == "REJECTED"
    assert client.get(f"/api/plantations/{review['id']}", headers=farmer).json()["status"] == "REJECTED"
    assert client.post(f"/api/plantations/{review['id']}/generate-credits", headers=farmer, json={}).status_code == 409


def test_auditor_rules(client, actors):
    farmer, _, auditor = actors
    pending = client.post("/api/plantations", headers=farmer, json=plantation_payload()).json()
    pv = client.post(f"/api/plantations/{pending['id']}/verify", headers=farmer).json()
    r = client.post(f"/api/admin/verifications/{pv['id']}/decision", headers=auditor, json={"decision": "APPROVED", "notes": "x"})
    assert r.status_code == 400 and "not fully scored" in r.json()["detail"]
    assert client.post(f"/api/admin/verifications/{pv['id']}/decision", headers=auditor, json={"decision": "MAYBE"}).status_code == 422
    assert client.post("/api/admin/verifications/VER-NOPE/decision", headers=auditor, json={"decision": "REJECTED", "notes": "x"}).status_code == 404

    review = make_scored_plantation(client, farmer, **TEST_NDVI)
    v1 = client.post(f"/api/plantations/{review['id']}/verify", headers=farmer).json()
    # Override without notes is refused
    r = client.post(f"/api/admin/verifications/{v1['id']}/decision", headers=auditor, json={"decision": "APPROVED"})
    assert r.status_code == 422
    # Superseded verification cannot be decided
    v2 = client.post(f"/api/plantations/{review['id']}/verify", headers=farmer).json()
    r = client.post(f"/api/admin/verifications/{v1['id']}/decision", headers=auditor, json={"decision": "APPROVED", "notes": "ok"})
    assert r.status_code == 409
    # Approve latest with notes → credit issued and listed, decision is auditable
    r = client.post(f"/api/admin/verifications/{v2['id']}/decision", headers=auditor,
                    json={"decision": "APPROVED", "notes": "Checked reported NDVI against Copernicus Browser"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"] == "APPROVED" and body["engine_decision"] == "REVIEW"
    assert body["decided_by"].endswith("@test.example") and "Copernicus" in body["auditor_notes"]
    credit = next(c for c in client.get("/api/marketplace/credits").json() if c["plantation_id"] == review["id"])
    assert credit["ndvi_provenance"] == "REPORTED"
    # Final once credits exist
    r = client.post(f"/api/admin/verifications/{v2['id']}/decision", headers=auditor, json={"decision": "REJECTED", "notes": "changed mind"})
    assert r.status_code == 409
    logs = client.get("/api/admin/audit-logs", headers=auditor).json()
    assert any(l["action"] == "AUDITOR_DECISION" and l["target_id"] == v2["id"] for l in logs)


def test_queue_shows_previews_for_unverified(client, actors):
    farmer, _, auditor = actors
    p = client.post("/api/plantations", headers=farmer, json=plantation_payload()).json()
    queue = client.get("/api/admin/verifications", headers=auditor).json()
    item = next(i for i in queue if i["plantation_id"] == p["id"])
    assert item["id"] is None and item["is_persisted"] is False and item["decision"] == "PENDING"
    assert item["overall_score"] is None and item["missing_evidence"]


def test_purchase_guards(client, actors, computed_ndvi):
    farmer, buyer, _ = actors
    _, _, credit = _approved_credit(client, farmer)
    cid, lot = credit["id"], credit["carbon_quantity_tco2e"]

    assert client.post("/api/marketplace/credits/CC-DOES-NOT-EXIST/purchase", headers=buyer, json={}).status_code == 404
    assert client.post(f"/api/marketplace/credits/{cid}/purchase", headers=buyer, json={"quantity_tco2e": -1}).status_code == 422
    assert client.post(f"/api/marketplace/credits/{cid}/purchase", headers=buyer, json={"quantity_tco2e": 0}).status_code == 422
    over = client.post(f"/api/marketplace/credits/{cid}/purchase", headers=buyer, json={"quantity_tco2e": lot + 1})
    assert over.status_code == 422 and "exceeds" in over.json()["detail"]
    partial = client.post(f"/api/marketplace/credits/{cid}/purchase", headers=buyer, json={"quantity_tco2e": lot / 2})
    assert partial.status_code == 422 and "whole lots" in partial.json()["detail"]

    ok = client.post(f"/api/marketplace/credits/{cid}/purchase", headers=buyer, json={"quantity_tco2e": lot})
    assert ok.status_code == 201, ok.text
    txn = ok.json()
    assert txn["total_amount"] == pytest.approx(lot * credit["price_per_tco2e"])
    assert txn["blockchain_status"] == "NOT_RECORDED" and txn["blockchain_tx_hash"] is None
    assert "no real payment" in txn["notes"]

    # Duplicate purchase by the same or another buyer
    assert client.post(f"/api/marketplace/credits/{cid}/purchase", headers=buyer, json={}).status_code == 400
    other, _ = register(client, "BUYER")
    assert client.post(f"/api/marketplace/credits/{cid}/purchase", headers=other, json={}).status_code == 409
    assert cid not in listed_ids(client)
    detail = client.get(f"/api/marketplace/credits/{cid}").json()
    assert detail["status"] == "SOLD" and detail["is_listed"] is False

    # Retire: only owner, only once
    assert client.post(f"/api/marketplace/credits/{cid}/retire", headers=other).status_code == 403
    r = client.post(f"/api/marketplace/credits/{cid}/retire", headers=buyer)
    assert r.status_code == 200 and r.json()["blockchain_status"] == "NOT_RECORDED"
    assert client.post(f"/api/marketplace/credits/{cid}/retire", headers=buyer).status_code == 409
    assert client.post(f"/api/marketplace/credits/{cid}/purchase", headers=other, json={}).status_code == 409

    txns = client.get("/api/transactions", headers=buyer).json()
    assert [t["credit_id"] for t in txns] == [cid]
    assert client.get("/api/transactions", headers=farmer).json()[0]["id"] == txn["id"]


def test_concurrent_purchases_only_one_succeeds(client, actors, computed_ndvi, api_base):
    import requests
    farmer, _, _ = actors
    _, _, credit = _approved_credit(client, farmer)
    buyers = [register(client, "BUYER")[0] for _ in range(5)]
    codes = []

    def buy(h):
        codes.append(requests.post(f"{api_base}/marketplace/credits/{credit['id']}/purchase", headers=h, json={}).status_code)

    threads = [threading.Thread(target=buy, args=(h,)) for h in buyers]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert codes.count(201) == 1 and codes.count(409) == 4, codes


def test_legacy_or_superseded_credits_not_listed(client, actors, computed_ndvi):
    farmer, buyer, _ = actors
    _, v, credit = _approved_credit(client, farmer)
    assert credit["id"] in listed_ids(client)
    db = SessionLocal()
    try:
        ver = db.get(Verification, v["id"])
        ver.ndvi_provenance = None  # simulate a pre-fix (legacy) verification record
        db.commit()
    finally:
        db.close()
    assert credit["id"] not in listed_ids(client)
    r = client.post(f"/api/marketplace/credits/{credit['id']}/purchase", headers=buyer, json={})
    assert r.status_code == 409 and "legacy" in r.json()["detail"]


def test_status_filter_validation(client):
    assert client.get("/api/marketplace/credits", params={"status_filter": "PENDING"}).status_code == 422
    assert client.get("/api/marketplace/credits", params={"min_score": 101}).status_code == 422
