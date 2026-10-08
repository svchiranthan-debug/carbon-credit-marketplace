"""
Ethereum audit layer for carbon credits (CarbonCreditRegistry on a local Ganache chain).

What is real here:
  * When Ganache is reachable, credits are issued, transferred and retired by sending real
    transactions to the deployed CarbonCreditRegistry contract; tx hashes come from mined
    receipts.

What is NOT real / is a prototype simplification:
  * Users have no wallets. Each user is mapped to one of Ganache's unlocked development
    accounts (custodial demo addresses) and the backend signs everything with account[0],
    the contract admin.
  * The contract's ``carbonQuantity`` field holds kilograms of CO2e (tCO2e × 1000) so that
    fractional tonnages are stored exactly.

Failure policy: if the chain is disabled or unreachable, or a transaction reverts, the
result has ``status`` NOT_RECORDED or FAILED and ``tx_hash`` None. A transaction hash is
never invented.
"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import settings

try:
    from web3 import Web3
except ImportError:  # web3 is optional; without it the chain is simply unavailable
    Web3 = None

logger = logging.getLogger(__name__)

STATUS_CONFIRMED = "CONFIRMED"
STATUS_NOT_RECORDED = "NOT_RECORDED"
STATUS_FAILED = "FAILED"

KG_PER_TONNE = 1000


def _hex(value: Any) -> str:
    h = value.hex() if hasattr(value, "hex") else str(value)
    return h if h.startswith("0x") else f"0x{h}"


class BlockchainService:
    _w3 = None
    _contract = None
    _contract_address: Optional[str] = None
    _abi = None

    CONTRACTS_DIR = Path(__file__).resolve().parent.parent.parent / "contracts"
    CONTRACT_ARTIFACT_PATH = CONTRACTS_DIR / "CarbonCreditRegistry.json"
    DEPLOYED_ADDR_PATH = CONTRACTS_DIR / "deployed_address.txt"

    # ------------------------------------------------------------------ connection
    @classmethod
    def get_w3(cls):
        if not settings.ENABLE_BLOCKCHAIN or Web3 is None:
            return None
        if cls._w3 is not None:
            try:
                if cls._w3.is_connected():
                    return cls._w3
            except Exception:
                pass
            cls._w3 = cls._contract = None
        try:
            w3 = Web3(Web3.HTTPProvider(settings.ETHEREUM_RPC_URL, request_kwargs={"timeout": 5}))
            if w3.is_connected():
                cls._w3 = w3
        except Exception as exc:
            logger.info("Ethereum node not reachable at %s: %s", settings.ETHEREUM_RPC_URL, exc)
        return cls._w3

    @classmethod
    def status(cls) -> Dict[str, Any]:
        w3 = cls.get_w3()
        contract = cls.get_contract() if w3 else None
        return {
            "enabled": settings.ENABLE_BLOCKCHAIN,
            "web3_installed": Web3 is not None,
            "rpc_url": settings.ETHEREUM_RPC_URL,
            "connected": w3 is not None,
            "chain_id": w3.eth.chain_id if w3 else None,
            "contract_address": cls._contract_address if contract else None,
        }

    @classmethod
    def deploy_contract(cls, force_new: bool = False):
        w3 = cls.get_w3()
        if not w3 or not cls.CONTRACT_ARTIFACT_PATH.exists():
            return None
        try:
            artifact = json.loads(cls.CONTRACT_ARTIFACT_PATH.read_text())
            cls._abi = artifact["abi"]

            address = None
            if not force_new and cls.DEPLOYED_ADDR_PATH.exists():
                saved = cls.DEPLOYED_ADDR_PATH.read_text().strip()
                if w3.is_address(saved) and len(w3.eth.get_code(Web3.to_checksum_address(saved))) > 0:
                    address = Web3.to_checksum_address(saved)

            if not address:
                if not w3.eth.accounts:
                    return None
                factory = w3.eth.contract(abi=cls._abi, bytecode=artifact["bytecode"])
                receipt = w3.eth.wait_for_transaction_receipt(
                    factory.constructor().transact({"from": w3.eth.accounts[0]}), timeout=30
                )
                address = receipt.contractAddress
                cls.DEPLOYED_ADDR_PATH.write_text(address)
                logger.info("CarbonCreditRegistry deployed at %s", address)

            cls._contract_address = address
            cls._contract = w3.eth.contract(address=address, abi=cls._abi)
            return cls._contract
        except Exception as exc:
            logger.warning("Could not initialise CarbonCreditRegistry: %s", exc)
            cls._contract = None
            return None

    @classmethod
    def get_contract(cls):
        w3 = cls.get_w3()
        if not w3:
            return None
        if cls._contract is not None:
            try:
                if len(w3.eth.get_code(cls._contract_address)) > 0:
                    return cls._contract
            except Exception:
                pass
            cls._contract = None  # chain was reset; redeploy / reload below
        return cls.deploy_contract(force_new=False)

    @classmethod
    def address_for_user(cls, user_id: Optional[int]) -> Optional[str]:
        """Deterministic custodial demo address for a platform user (Ganache account 1..n-1)."""
        w3 = cls.get_w3()
        if not w3:
            return None
        accounts = w3.eth.accounts
        if len(accounts) < 2:
            return accounts[0] if accounts else None
        return accounts[1 + ((user_id or 0) % (len(accounts) - 1))]

    # ------------------------------------------------------------------ hashing
    @classmethod
    def compute_report_hash(cls, verification: Any) -> str:
        """SHA-256 over the verification's identity, score, decision and evidence snapshot."""
        if hasattr(verification, "id"):
            payload = {
                "id": verification.id,
                "plantation_id": verification.plantation_id,
                "overall_score": verification.overall_score,
                "decision": verification.decision,
                "evidence_snapshot": getattr(verification, "evidence_snapshot", None),
            }
        elif isinstance(verification, dict):
            payload = {k: verification.get(k) for k in ("id", "plantation_id", "overall_score", "decision", "evidence_snapshot")}
        else:
            payload = {"value": str(verification)}
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------ transactions
    @classmethod
    def _unavailable(cls, reason: str) -> Dict[str, Any]:
        return {"status": STATUS_NOT_RECORDED, "tx_hash": None, "block_number": None,
                "contract_address": None, "reason": reason}

    @classmethod
    def _send(cls, fn_name: str, *args) -> Dict[str, Any]:
        contract = cls.get_contract()
        w3 = cls.get_w3()
        if not w3:
            return cls._unavailable("Blockchain disabled or node unreachable.")
        if not contract:
            return cls._unavailable("CarbonCreditRegistry contract unavailable.")
        try:
            tx = getattr(contract.functions, fn_name)(*args).transact({"from": w3.eth.accounts[0]})
            receipt = w3.eth.wait_for_transaction_receipt(tx, timeout=30)
            if receipt.status != 1:
                return {"status": STATUS_FAILED, "tx_hash": _hex(receipt.transactionHash), "block_number": receipt.blockNumber,
                        "contract_address": cls._contract_address, "reason": "Transaction reverted."}
            return {"status": STATUS_CONFIRMED, "tx_hash": _hex(receipt.transactionHash),
                    "block_number": receipt.blockNumber, "contract_address": cls._contract_address, "reason": None}
        except Exception as exc:
            logger.warning("On-chain %s failed: %s", fn_name, exc)
            return {"status": STATUS_FAILED, "tx_hash": None, "block_number": None,
                    "contract_address": cls._contract_address, "reason": f"{exc.__class__.__name__}: {exc}"[:300]}

    @classmethod
    def register_credit_on_chain(cls, credit_id: str, plantation_id: int, carbon_quantity_tco2e: float,
                                 report_hash: str, owner_user_id: Optional[int] = None) -> Dict[str, Any]:
        contract = cls.get_contract()
        if contract is not None:
            try:
                if contract.functions.creditExists(credit_id).call():
                    return {"status": STATUS_FAILED, "tx_hash": None, "block_number": None,
                            "contract_address": cls._contract_address,
                            "reason": "Credit ID already registered on-chain."}
            except Exception:
                pass
        owner = cls.address_for_user(owner_user_id)
        qty_kg = int(round(carbon_quantity_tco2e * KG_PER_TONNE))
        res = cls._send("issueCredit", credit_id, int(plantation_id), qty_kg, report_hash, owner) if owner else \
            cls._unavailable("Blockchain disabled or node unreachable.")
        res["owner_address"] = owner if res["status"] == STATUS_CONFIRMED else None
        return res

    @classmethod
    def transfer_credit_on_chain(cls, credit_id: str, new_owner_user_id: Optional[int] = None) -> Dict[str, Any]:
        new_owner = cls.address_for_user(new_owner_user_id)
        if not new_owner:
            return cls._unavailable("Blockchain disabled or node unreachable.")
        res = cls._send("transferCredit", credit_id, new_owner)
        res["owner_address"] = new_owner if res["status"] == STATUS_CONFIRMED else None
        return res

    @classmethod
    def retire_credit_on_chain(cls, credit_id: str) -> Dict[str, Any]:
        return cls._send("retireCredit", credit_id)

    @classmethod
    def get_on_chain_record(cls, credit_id: str) -> Optional[Dict[str, Any]]:
        contract = cls.get_contract()
        if not contract:
            return None
        try:
            if not contract.functions.creditExists(credit_id).call():
                return None
            d = contract.functions.getCredit(credit_id).call()
            return {
                "credit_id": d[0],
                "plantation_id": d[1],
                "carbon_quantity_tco2e": d[2] / KG_PER_TONNE,
                "report_hash": d[3],
                "owner_address": d[4],
                "issued_at_timestamp": d[5],
                "is_retired": bool(d[6]),
                "retired_at_timestamp": d[7],
                "contract_address": cls._contract_address,
            }
        except Exception as exc:
            logger.warning("getCredit failed: %s", exc)
            return None
