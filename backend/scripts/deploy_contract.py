#!/usr/bin/env python3
"""
Deploy (or re-use) the CarbonCreditRegistry contract on the configured Ethereum node.

    python scripts/deploy_contract.py           # re-use the address in contracts/deployed_address.txt if it still has code
    python scripts/deploy_contract.py --new     # always deploy a fresh instance

Requires a running node at ETHEREUM_RPC_URL (default http://127.0.0.1:8545), e.g.:
    npx ganache@7.9.2 --wallet.deterministic --chain.chainId 1337
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.blockchain_service import BlockchainService  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--new", action="store_true", help="deploy a new contract instance")
args = parser.parse_args()

if BlockchainService.get_w3() is None:
    sys.exit("No Ethereum node reachable (check ETHEREUM_RPC_URL / ENABLE_BLOCKCHAIN, and that web3 is installed).")
contract = BlockchainService.deploy_contract(force_new=args.new)
if contract is None:
    sys.exit("Deployment failed; see log output above.")
print(json.dumps(BlockchainService.status(), indent=2))
