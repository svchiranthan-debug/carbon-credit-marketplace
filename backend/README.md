# Backend — FastAPI

The API, verification engine, ML classifier, SQLite database and blockchain integration for the Carbon Credit Marketplace.

## Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| Python | 3.11 – 3.13 | everything |
| Node.js | 18+ | only to run Ganache (local blockchain) |
| Ganache | 7.9.x (`npx ganache@7.9.2`) | optional: on-chain credit records |

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # torch/torchvision are large; first install takes a while
cp .env.example .env                 # then set SECRET_KEY (see below)
python seed_data.py                  # demo accounts + one boundary-only plantation
```

`seed_data.py` never deletes anything. `python seed_data.py --reset` drops all tables first (it asks for confirmation).

### Database

SQLite by default, at `backend/carbon_marketplace.db` (git-ignored). Tables are created on startup by `init_db()` in `app/database.py`, which also adds any columns that newer code expects to an older database file (additive only; it never drops data). Foreign keys are enforced (`PRAGMA foreign_keys=ON`).

To inspect an older database for records made before the evidence-integrity fixes (read-only):

```bash
python scripts/audit_legacy_data.py
```

### Environment variables

All have development defaults (`app/config.py`); set them in `backend/.env` or the shell.

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | dev-only value (warning logged) | JWT signing key. **Set this** for anything shared. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Login session length |
| `DATABASE_URL` | `sqlite:///backend/carbon_marketplace.db` | SQLAlchemy URL |
| `UPLOAD_DIR` | `backend/uploads` | Where ground photos are stored |
| `CORS_ORIGINS` | `*` | Comma-separated allowed browser origins |
| `ENABLE_REAL_SATELLITE_QUERIES` | `true` | Compute NDVI from Sentinel-2 (Microsoft Planetary Computer) |
| `PLANETARY_COMPUTER_API_KEY` | empty | Optional subscription key |
| `ENABLE_BLOCKCHAIN` | `true` | Record credits on the contract when a node is reachable |
| `ETHEREUM_RPC_URL` | `http://127.0.0.1:8545` | Ganache / dev node |

## Run

```bash
# optional, in another terminal: local blockchain
npx ganache@7.9.2 --wallet.deterministic --chain.chainId 1337
python scripts/deploy_contract.py          # deploys CarbonCreditRegistry (or re-uses a live one)

# API (use --host 0.0.0.0 so phones on the same Wi-Fi can reach it)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API base URL: `http://localhost:8000/api`
- Interactive docs (Swagger): `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`, chain status: `http://localhost:8000/api/blockchain/status`

Demo accounts (password `Demo@123`): `farmer@agrocarbon.demo`, `farmer2@agrocarbon.demo`, `buyer@ecocorp.demo`, `buyer2@greeninvest.demo`, `auditor@agrocarbon.demo`, `admin@agrocarbon.demo`. Public registration allows FARMER and BUYER only. AUDITOR accounts are created by an ADMIN (`POST /api/users`, or the admin dashboard form). ADMIN accounts come from `seed_data.py`.

## Tests

```bash
pytest            # from backend/, ~30 s
```

Tests use a throw-away database and uploads folder (never your real DB), run a real uvicorn server in a background thread for the HTTP tests, and keep satellite access off. The real-chain tests in `tests/test_blockchain.py` run only if Ganache is listening on `GANACHE_URL` (default `http://127.0.0.1:8545`); otherwise they are reported as skipped.

## Layout

```
app/
  main.py                 FastAPI app, CORS, /uploads static files, router registration
  config.py               Settings (env / .env)
  database.py             Engine, session, init_db() + additive migrations
  core/security.py        bcrypt hashing, JWT, role checks
  models/                 User, Plantation, Verification, Credit, Transaction, AuditLog
  schemas/schemas.py      Pydantic request/response models and validation
  routers/                auth, users, plantations, verification, carbon, marketplace, transactions, admin
  services/
    verification_engine.py   PENDING → APPROVED/REVIEW/REJECTED rules, reasons, evidence snapshot
    verification_store.py    persisting / reading verifications
    marketplace_rules.py     the single listing rule used by list + purchase
    carbon_engine.py         sequestration estimate and credit issuance guards
    risk_engine.py           fraud / consistency checks
    blockchain_service.py    CarbonCreditRegistry via web3 (Ganache)
    ai/                      satellite_client (Sentinel-2), ndvi_service, ai_vision_service (MobileNetV3), cv_service, soc_service
contracts/                CarbonCreditRegistry.sol + compiled ABI/bytecode, compile_contract.js
ml/                       prepare_dataset.py (synthetic images), train.py, evaluate.py, weights/
scripts/                  deploy_contract.py, sync_blockchain.py, audit_legacy_data.py, check_geocoding.py
tests/                    pytest suite
```

## How verification decides

`Score = 0.40 × NDVI + 0.35 × CV + 0.25 × SOC` → **APPROVED** ≥ 75, **REVIEW** ≥ 55, **REJECTED** < 55.

1. Boundary (drawn polygon, or centre + area), a decodable ground photo and an SOC value are required. If any is missing → **PENDING**, all scores null.
2. NDVI comes from Sentinel-2 pixels read by the backend (`SENTINEL2_COMPUTED`) or from a reported value with source and date (`REPORTED`). If neither is available → **PENDING**. Nothing is simulated. Only pixels inside the drawn polygon count, and pixels the scene classification layer marks as cloud, shadow, cirrus, snow or no-data are dropped. A scene is used only if at least 50% of the plot is clear.
3. If the photo model cannot run (missing weights, corrupt image) → **PENDING**.
4. HIGH fraud risk or REPORTED NDVI turn an APPROVED result into **REVIEW**, so an auditor must confirm it.
5. Every verification stores `decision_reasons`, `evidence_snapshot` (inputs + photo SHA-256), `ndvi_provenance`, `engine_decision`, `decided_by` and `auditor_notes`.
6. Credits are minted only from the plantation's latest APPROVED, fully scored verification. After that, evidence and the decision are locked.

## Blockchain: what is real and what is not

| | Status |
|---|---|
| Contract `CarbonCreditRegistry` (issue / transfer / retire / getCredit) | **Implemented**; ABI and bytecode match `solc 0.8.20` with the optimizer off (`contracts/compile_contract.js` regenerates them) |
| Issue on approval, transfer on purchase, retire | **Implemented**: real transactions, hashes from mined receipts |
| Quantities | Stored on-chain in **kg CO2e** (tCO2e × 1000) so fractions are exact |
| Wallets | **Prototype**: users have no wallets; each user maps to a Ganache dev account, and the backend signs with account 0 (contract admin) |
| Chain offline | Credits are marked `NOT_RECORDED` with no hash; `scripts/sync_blockchain.py --apply` registers still-unsold ones later |
| Payments | **Not implemented**: purchases are prototype transactions, no money moves |

Ganache keeps state in memory: after a restart, run `python scripts/deploy_contract.py` again; earlier credits then read as `DATABASE_ONLY` on the credit page.
