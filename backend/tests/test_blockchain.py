"""Task 8: blockchain layer.

* Offline behaviour is always tested: no tx hash is ever invented.
* Real-chain tests run only when a Ganache/Ethereum dev node is reachable at
  GANACHE_URL (default http://127.0.0.1:8545); otherwise they are skipped, not faked.
"""
import os

import pytest

from app.config import settings
from app.services.blockchain_service import BlockchainService
from conftest import make_scored_plantation, register

GANACHE_URL = os.environ.get("GANACHE_URL", "http://127.0.0.1:8545")


def _reset_cache():
    BlockchainService._w3 = None
    BlockchainService._contract = None
    BlockchainService._contract_address = None


def test_offline_results_are_not_recorded(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_BLOCKCHAIN", False)
    _reset_cache()
    for res in (
        BlockchainService.register_credit_on_chain("CC-X", 1, 2.5, "abc", owner_user_id=1),
        BlockchainService.transfer_credit_on_chain("CC-X", new_owner_user_id=2),
        BlockchainService.retire_credit_on_chain("CC-X"),
    ):
        assert res["status"] == "NOT_RECORDED" and res["tx_hash"] is None
    assert BlockchainService.get_on_chain_record("CC-X") is None
    assert BlockchainService.status()["connected"] is False


def test_unreachable_node_is_not_recorded(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_BLOCKCHAIN", True)
    monkeypatch.setattr(settings, "ETHEREUM_RPC_URL", "http://127.0.0.1:1")
    _reset_cache()
    res = BlockchainService.register_credit_on_chain("CC-Y", 1, 2.5, "abc", owner_user_id=1)
    assert res["status"] == "NOT_RECORDED" and res["tx_hash"] is None
    _reset_cache()


def _ganache_up() -> bool:
    try:
        import requests
        r = requests.post(GANACHE_URL, json={"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1}, timeout=2)
        return r.status_code == 200
    except Exception:
        return False


@pytest.fixture
def chain(monkeypatch, tmp_path):
    if not _ganache_up():
        pytest.skip(f"No Ethereum dev node at {GANACHE_URL} (start Ganache to run real-chain tests)")
    monkeypatch.setattr(settings, "ENABLE_BLOCKCHAIN", True)
    monkeypatch.setattr(settings, "ETHEREUM_RPC_URL", GANACHE_URL)
    # Keep the developer's deployed_address.txt untouched
    monkeypatch.setattr(BlockchainService, "DEPLOYED_ADDR_PATH", tmp_path / "deployed_address.txt")
    _reset_cache()
    yield
    _reset_cache()


def test_full_lifecycle_on_real_chain(client, chain, computed_ndvi):
    farmer, _ = register(client, "FARMER")
    buyer, buyer_user = register(client, "BUYER")
    p = make_scored_plantation(client, farmer)
    v = client.post(f"/api/plantations/{p['id']}/verify", headers=farmer).json()
    assert v["decision"] == "APPROVED"
    credit = next(c for c in client.get("/api/marketplace/my-credits", headers=farmer).json() if c["plantation_id"] == p["id"])
    assert credit["blockchain_status"] == "CONFIRMED"
    assert credit["blockchain_tx_hash"].startswith("0x") and len(credit["blockchain_tx_hash"]) == 66

    rec = client.get(f"/api/marketplace/credits/{credit['id']}/blockchain-record").json()
    assert rec["on_chain"] is True and rec["source"] == "CONTRACT"
    assert rec["carbon_quantity_tco2e"] == pytest.approx(credit["carbon_quantity_tco2e"])  # stored as kg, exact
    assert rec["report_hash"] == credit["report_hash"]
    farmer_addr = rec["owner_address"]

    txn = client.post(f"/api/marketplace/credits/{credit['id']}/purchase", headers=buyer, json={}).json()
    assert txn["blockchain_status"] == "CONFIRMED" and txn["blockchain_tx_hash"].startswith("0x")
    rec2 = client.get(f"/api/marketplace/credits/{credit['id']}/blockchain-record").json()
    assert rec2["owner_address"] == BlockchainService.address_for_user(buyer_user["id"])

    r = client.post(f"/api/marketplace/credits/{credit['id']}/retire", headers=buyer).json()
    assert r["blockchain_status"] == "CONFIRMED"
    rec3 = client.get(f"/api/marketplace/credits/{credit['id']}/blockchain-record").json()
    assert rec3["is_retired"] is True and rec3["status"] == "RETIRED"


def test_double_registration_is_refused_by_contract(chain):
    first = BlockchainService.register_credit_on_chain("CC-DUP-TEST", 1, 1.234, "h", owner_user_id=1)
    assert first["status"] == "CONFIRMED"
    second = BlockchainService.register_credit_on_chain("CC-DUP-TEST", 1, 1.234, "h", owner_user_id=1)
    assert second["status"] == "FAILED" and second["tx_hash"] is None
    assert BlockchainService.get_on_chain_record("CC-DUP-TEST")["carbon_quantity_tco2e"] == pytest.approx(1.234)
