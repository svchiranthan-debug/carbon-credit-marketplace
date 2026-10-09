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
| `MAX_PHOTOS_PER_PLANTATION` | `10` | Active ground photos per plantation |
| `PHOTO_URL_TTL_S` | `3600` | Lifetime of signed photo links |
| `CV_LOW_CONFIDENCE_PCT` | `60` | Photos below this classifier confidence count as low-confidence |
| `PHOTO_NEAR_DUPLICATE_DISTANCE` | `6` | pHash distance at or below which two photos of a plot are near-duplicates |
| `SATELLITE_LOOKBACK_DAYS` | `120` | Scene search window (days before today) |
| `SATELLITE_MAX_SCENE_CLOUD_PCT` | `20` | Scene-level cloud cover limit (`eo:cloud_cover`) |
| `SATELLITE_MAX_SCENES_TRIED` | `3` | Least-cloudy scenes tried before NDVI is reported unavailable |
| `SATELLITE_MAX_ATTEMPTS` | `3` | Attempts per request on timeouts, connection errors and HTTP 429/5xx (other errors are not retried) |
| `SATELLITE_RETRY_BACKOFF_S` | `1.0` | First retry wait; doubles each retry. `Retry-After` is honoured (max 10 s) |
| `SATELLITE_REQUEST_TIMEOUT_S` | `20` | Per-request timeout (catalogue, token, band reads) |
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

Demo accounts (password `Demo@123`): `farmer@agrocarbon.demo`, `farmer2@agrocarbon.demo`, `buyer@ecocorp.demo`, `buyer2@greeninvest.demo`, `auditor@agrocarbon.demo`, `admin@agrocarbon.demo`. Public registration allows FARMER, BUYER and AUDITOR. ADMIN accounts come from `seed_data.py`; an ADMIN can also create accounts with `POST /api/users` (or the admin dashboard form).

## Ground photos (multi-photo evidence)

A plantation can have up to 10 ground photos (`plantation_photos` table, created automatically; older single-photo plantations get a photo row on startup, nothing is deleted).

| Endpoint | Who | Purpose |
|---|---|---|
| `POST /api/plantations/{id}/photos` | owning farmer | Add ONE photo (send several requests for several photos, so each has its own status and can be retried) |
| `GET /api/plantations/{id}/photos` | owner, auditor, admin (buyers: verified plots only) | All active photos with per-photo classifier result, warnings and a signed link |
| `DELETE /api/plantations/{id}/photos/{photo_id}` | owning farmer | Withdraw a photo before verification (file is kept for audit) |
| `POST /api/plantations/{id}/image`, `PUT …/evidence {image_url}`, `POST /upload-image` | as before | Older clients: each call **adds** a photo |

- A file is accepted only if it decodes as JPEG/PNG/WEBP/TIFF (the extension and MIME type are not trusted), is within `MAX_UPLOAD_BYTES`, and is not an exact copy of a photo already on the plot. Rejected uploads leave no file behind.
- Photos are **not public**: `/uploads/<file>` only serves signed links (`?exp=…&sig=…`) that the API gives to users allowed to see the plantation. Links expire after 1–2 hours.
- Evidence is locked once credits are issued.

**How the photo (CV) score is formed.** The existing classifier runs on every valid photo, and each result is stored on the photo and in the verification's `evidence_snapshot.photos`. Near-duplicates (pHash) count once. The CV score is the **lower median** of the unique photos' scores: one good photo cannot lift poor or unrelated ones, and scores are never added up. If the photos disagree (plantation vs. confident non-plantation) or confidence is low (< 60% for the median photo or for most photos), an APPROVED result is capped at REVIEW. With no scorable photo the plot stays PENDING. Extra photos never replace missing NDVI or soil data. Weights and thresholds are unchanged.

## Live satellite check

The automated tests mock Planetary Computer. To check the real service from a computer with internet access:

```bash
python scripts/check_live_ndvi.py                          # demo 1-acre plot
python scripts/check_live_ndvi.py --plantation-id 3         # a plot from your DB (uses its drawn boundary)
python scripts/check_live_ndvi.py --plantation-id 3 --persist   # also runs and saves a real verification
```

It prints PASS/FAIL for each stage (catalogue search → SAS token → B04/B08/SCL window reads → polygon and cloud mask → NDVI) and the scene ID, acquisition date and NDVI summary. It only reports success when real band pixels were read.

How access works: one SAS token for `sentinel-2-l2a` is fetched from `/api/sas/v1/token/sentinel-2-l2a`, cached until 5 minutes before its `msft:expiry`, and appended to each band URL. If blob storage answers 403 (expired or rejected signature), the token is refreshed once and the read retried. Error messages name the failing stage and HTTP status; signatures are removed from them.

## Ground-photo model

`ml/weights/plantation_classifier_v2.pt` is trained on real photographs and scores 98.4% on held-out real test photos (`ml/reports/evaluation_v2.md`). To rebuild it (~12 minutes on a laptop CPU):

```bash
python ml/build_real_dataset.py   # downloads the source photos (~500 MB git cache) into ml/dataset_real/
python ml/train.py                # writes v2 weights, metadata and the evaluation report
python ml/evaluate.py             # re-checks any checkpoint on the real test split
```

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
ml/                       build_real_dataset.py (real photos), train.py, evaluate.py, weights/, reports/
                          (prepare_dataset.py only makes synthetic images for tests)
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
