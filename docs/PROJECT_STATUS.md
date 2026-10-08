# Project Status Report

Audited 2026-10-08 · covers PR #1 (tasks 1–12), PR #2 (auditors, boundary, clouds) and PR #3 (real-photo model, mobile boundary, cleanup)

| Area | Result |
|---|---|
| BACKEND | **PASS** |
| DATABASE | **PASS** |
| ML | **PASS**: retrained on real photos, 98.4% on a held-out real test set (not yet tested on real plantation photos) |
| VERIFICATION | **PASS** |
| FRONTEND | **PASS** |
| MOBILE | **PASS**: typecheck, Android bundle and Metro start; not run on a physical device here |
| BLOCKCHAIN | **PASS** |
| TESTS | **PASS** (88 passed with Ganache; 86 passed + 2 skipped without it) |
| DOCUMENTATION | **PASS** |

## How this was checked

| Check | Command | Result |
|---|---|---|
| Fresh clone → install → seed → start | `pip install -r requirements.txt && python seed_data.py && uvicorn app.main:app` | Started; `/api/health` 200; `/docs` 200 |
| Backend tests (with Ganache 7.9.2) | `cd backend && pytest` | 88 passed |
| Backend tests (no chain) | same | 86 passed, 2 skipped (real-chain tests) |
| Ground-photo model on held-out real photos | `python ml/evaluate.py` | v2: accuracy 0.984 (v1: 0.496) |
| Contract artifact vs source | `node contracts/compile_contract.js` (solc 0.8.20, optimizer off) | ABI and bytecode match the committed artifact |
| Frontend build / lint | `npm run build`, `npm run lint` | Build OK, largest chunk 223 kB; 0 lint errors, 0 warnings |
| Frontend in a browser | Playwright against the dev server + demo backend | Verification Wall checked for approved, incomplete, rejected and missing-NDVI plots; error banner shown when the backend is down |
| Mobile | `npx tsc --noEmit`, `npx expo export --platform android`, `npx expo start` | Typecheck OK; bundle OK; Metro reports `packager-status:running` |

## End-to-end sequence (tests/test_e2e_journey.py, real HTTP)

Register → plantation (PENDING) → photo + SOC + reported NDVI → verify (REVIEW, reported NDVI) → auditor approves with notes → credit minted and listed → purchase → retire → DB state and audit log checked. Failure cases covered: missing evidence, invalid input (18 malformed payloads), incomplete project, failed verification (REJECTED), nonexistent project/credit, duplicate submission, invalid and oversized quantity, double purchase (including 5 concurrent buyers), backend unavailable.

## What was wrong and is now fixed

| Problem found | Where | Fix |
|---|---|---|
| When Sentinel-2 band files could not be read, a **random NDVI grid was generated and labelled "REAL SATELLITE DATA"** | `services/ai/satellite_client.py` | Real windowed read of B04/B08 with rasterio, otherwise *unavailable* |
| Coordinate-seeded **simulated NDVI was used for scoring and approval** | same | Removed; NDVI is either computed, reported (source + date, auditor required), or missing → PENDING |
| Hard-coded **"showcase" plot** given fixed NDVI/CV/SOC scores and a fake "real satellite" label | `services/verification_engine.py` | Removed |
| Fabricated historical NDVI diff and band reflectances | `services/ai/ndvi_service.py` | Removed |
| CV errors returned **default scores 30 / 50 / 60** | `ai_vision_service.py`, `cv_service.py` | Return null → PENDING with the reason |
| Zero-carbon plantations minted a **made-up 1 tCO2e** | `carbon_engine.py` | Issuance refused |
| Offline chain produced **fake "CONFIRMED" tx hashes**; record endpoint invented hashes and owner address | `blockchain_service.py`, `routers/transactions.py` | `NOT_RECORDED` / `FAILED`, no hash; DB-only records labelled `DATABASE_ONLY` |
| Marketplace listed any AVAILABLE credit (a legacy DB had one listed for a plantation in REVIEW) | `routers/marketplace.py` | One listing rule in `services/marketplace_rules.py`, used for listing and purchase |
| Partial-quantity purchase transferred the whole lot for a partial price; no negative/oversize checks; double purchase possible | `routers/transactions.py` | Whole-lot only, quantity validation, atomic compare-and-set |
| GET endpoints created and stored verification records | `routers/verification.py`, `routers/admin.py` | Read-only previews |
| Anyone could self-register as **ADMIN** | `routers/auth.py` | FARMER/BUYER/AUDITOR only |
| Risk engine exempted demo plots (ids 1–3, names with "Mandya") | `services/risk_engine.py` | Removed |
| SQLite foreign keys not enforced | `database.py` | `PRAGMA foreign_keys=ON` |
| Seed script dropped all tables and inserted pre-scored verifications and credits | `seed_data.py` | Only accounts + one boundary-only plot; `--reset` is explicit |
| Web: hard-coded tx hashes, contract addresses, "78.6" score, "52 tCO2e"; silent `.catch(() => [])`; evidence form pre-filled with SOC 1.80 / 45 cm / Red Sandy Loam | `frontend/src/pages/*` | Removed; real error states; empty form |
| Mobile: every login used password `Demo@123`; role switching without re-auth; hard-coded LAN IP 172.20.10.3; form pre-filled with SOC 1.85, area 1.8, 450 trees; hard-coded soil depth/type/age; canned auditor notes | `mobile/src/*` | Real login; role from backend; resolved dev address; empty form; auditor's own notes |
| Synthetic image generator crashed on non-square sizes | `ml/prepare_dataset.py` | Fixed shape (square training images unaffected) |

## ML model (PR #3)

The old classifier was trained only on computer-generated images and scored **49.6%** on real photos (it called almost every forest photo "non-plantation"). It has been replaced:

- **Data:** ~6,100 real training photos and 1,420 held-out real test photos from the Intel Image Classification dataset (`ml/build_real_dataset.py`, pinned to a fixed commit of a public GitHub mirror). plantation ← forest; non_plantation ← buildings, street, sea, glacier; unclear_evidence ← real photos with blur, darkness, over-exposure or occlusion added.
- **Result:** accuracy **98.4%**, macro F1 0.984 on the held-out test set (`ml/reports/evaluation_v2.md`). Training takes ~12 minutes on a laptop CPU.
- **Remaining gap:** the dataset has no areca, coconut or agroforestry photos, so "plantation" means "tree canopy". Accuracy on real plantation field photos is not measured yet; a small set of real farm photos would close that gap. The task brief mentions logistic regression; this project uses a CNN, which was kept.

## Open issues



| Issue | File | Recommended next step |
|---|---|---|
| Live Sentinel-2 path not exercised against the real service: this environment cannot reach Planetary Computer (the band-window code is tested on a local GeoTIFF) | `services/ai/satellite_client.py` | Run one verification on a networked laptop and check `ndvi_provenance = SENTINEL2_COMPUTED` |
| ~~NDVI over a square approximation; no cloud mask~~ **Fixed (PR #2, #3):** the drawn polygon is stored and used (web and mobile); SCL cloud/shadow/cirrus/snow pixels are excluded; ≥ 50% of the plot must be clear. Plots registered with only a GPS pin still use the square | `satellite_client.py` | — |
| Anyone can self-register as AUDITOR (kept on purpose: sign-in and sign-up work as in the original design). An ADMIN can also create auditors (`POST /api/users`, admin dashboard form) | `schemas/schemas.py` | For a real deployment, restrict AUDITOR sign-up to admins |
| Existing `carbon_marketplace.db` (from the zip, now untracked): 149 scored verifications with no NDVI provenance (74 labelled "REAL SATELLITE DATA" by the old synthetic-grid path) and 28 AVAILABLE credits, now hidden from the marketplace | local DB | Run `python scripts/audit_legacy_data.py`; start fresh with `seed_data.py --reset` if the old data is not needed |
| ~~Old default `SECRET_KEY` in git history~~ **Fixed (PR #3):** if no real key is configured, a random one is generated on first start and saved to `backend/.env` | `app/config.py` | — |
| Custodial demo wallets; backend signs all chain transactions | `blockchain_service.py` | Fine for a prototype; real wallets would need per-user keys |
| `GET /api/blockchain/status` deploys the contract if none is deployed | `blockchain_service.py` | Acceptable for local Ganache |
| ~~Frontend lint warnings and >500 kB bundle~~ **Fixed (PR #3):** pages are code-split; 0 lint warnings | `frontend/src` | — |
| ~~Desktop sidebar overlaps the header title~~ **Fixed (PR #2)** | `frontend/src/App.jsx` | — |
| Credits are sold as whole lots only (no partial purchases) | `routers/transactions.py`, contract | Deliberate: the contract has no split operation; adding one needs a contract change |
| Mobile app not run on a physical device in this audit | `mobile/` | Test with Expo Go on the same Wi-Fi as the backend |
