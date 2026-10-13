"""The auditor portal is about verification only: no buyer data or marketplace activity."""
import pytest

from conftest import TEST_NDVI, make_scored_plantation, register


@pytest.fixture
def actors(client):
    return register(client, "FARMER")[0], register(client, "BUYER")[0], register(client, "AUDITOR")[0]


def _sell_one_credit(client, farmer, buyer, computed_ndvi_fixture=None):
    p = make_scored_plantation(client, farmer)
    v = client.post(f"/api/plantations/{p['id']}/verify", headers=farmer).json()
    assert v["decision"] == "APPROVED", v["decision_reasons"]
    credit = client.post(f"/api/plantations/{p['id']}/generate-credits", headers=farmer, json={}).json()
    assert client.post(f"/api/marketplace/credits/{credit['id']}/purchase", headers=buyer, json={}).status_code == 201
    assert client.post(f"/api/marketplace/credits/{credit['id']}/retire", headers=buyer).status_code == 200
    return p, credit


def test_auditor_gets_no_buyer_data(client, actors, computed_ndvi):
    farmer, buyer, auditor = actors
    p, credit = _sell_one_credit(client, farmer, buyer)

    metrics = client.get("/api/admin/metrics", headers=auditor).json()
    for key in ("total_buyers", "total_transactions_count", "total_transaction_volume_inr"):
        assert key not in metrics
    assert metrics["credits_issued_count"] >= 1

    logs = client.get("/api/admin/audit-logs", headers=auditor).json()
    assert logs and all(l["user_role"] != "BUYER" for l in logs)
    assert not any(l["action"] in ("CREDIT_PURCHASE_COMPLETED", "CREDIT_RETIRED") for l in logs)

    assert client.get("/api/transactions", headers=auditor).status_code == 403
    assert client.get("/api/marketplace/my-credits", headers=auditor).status_code == 403

    # The verification shows that a credit was issued, without owner or sale status
    v = client.get(f"/api/plantations/{p['id']}/verification", headers=auditor).json()
    assert v["issued_credit_id"] == credit["id"] and v["issued_credit_tco2e"] == credit["carbon_quantity_tco2e"]
    assert "owner_id" not in v and "buyer_name" not in v


def test_buyers_and_farmers_still_see_their_own_data(client, actors, computed_ndvi):
    farmer, buyer, _ = actors
    _, credit = _sell_one_credit(client, farmer, buyer)
    assert any(t["credit_id"] == credit["id"] for t in client.get("/api/transactions", headers=buyer).json())
    assert any(t["credit_id"] == credit["id"] for t in client.get("/api/transactions", headers=farmer).json())
    assert any(c["id"] == credit["id"] for c in client.get("/api/marketplace/my-credits", headers=buyer).json())
