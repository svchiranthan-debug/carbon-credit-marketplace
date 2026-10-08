#!/usr/bin/env python3
"""
Record credits that were issued while the chain was offline (blockchain_status NOT_RECORDED/FAILED).

Only AVAILABLE credits still owned by the producing farmer are registered: for credits that were
already sold or retired off-chain, the on-chain history cannot be reconstructed truthfully, so they
are reported and left as they are.

    python scripts/sync_blockchain.py            # dry run
    python scripts/sync_blockchain.py --apply
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models.credit import Credit, CreditStatus  # noqa: E402
from app.models.plantation import Plantation  # noqa: E402
from app.services.blockchain_service import STATUS_CONFIRMED, BlockchainService  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()

init_db()
if BlockchainService.get_contract() is None:
    sys.exit("Contract unavailable: start Ganache and run scripts/deploy_contract.py first.")

db = SessionLocal()
try:
    pending = db.query(Credit).filter((Credit.blockchain_status.is_(None)) | (Credit.blockchain_status != STATUS_CONFIRMED)).all()
    for credit in pending:
        plantation = db.get(Plantation, credit.plantation_id)
        eligible = credit.status == CreditStatus.AVAILABLE.value and plantation and credit.owner_id == plantation.farmer_id
        if not eligible:
            print(f"SKIP {credit.id}: status {credit.status}; off-chain transfers cannot be replayed truthfully.")
            continue
        if not args.apply:
            print(f"WOULD REGISTER {credit.id} ({credit.carbon_quantity_tco2e} tCO2e)")
            continue
        res = BlockchainService.register_credit_on_chain(credit.id, credit.plantation_id, credit.carbon_quantity_tco2e,
                                                         credit.report_hash or "", owner_user_id=credit.owner_id)
        credit.blockchain_status = res["status"]
        credit.blockchain_tx_hash = res.get("tx_hash")
        credit.blockchain_contract_address = res.get("contract_address")
        db.commit()
        print(f"{res['status']} {credit.id} {res.get('tx_hash') or res.get('reason')}")
finally:
    db.close()
