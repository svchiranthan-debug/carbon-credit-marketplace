# Carbon Credit Marketplace with Multi-Modal Verification

> Final-year engineering project prototype. Smallholder agroforestry plots are verified using satellite NDVI, a ground-photo classifier and soil organic carbon. Only verified plots can issue carbon credits, which buyers can purchase and retire. Credits are recorded on a local Ethereum chain (Ganache).

**This is a prototype, not an accredited carbon registry.** See [Limitations](#limitations).

| Part | Folder | Stack |
|---|---|---|
| API, verification, ML, DB | [`backend/`](backend/README.md) | Python, FastAPI, SQLAlchemy 2 (SQLite), PyTorch MobileNetV3-Small, rasterio, web3.py |
| Web app | [`frontend/`](frontend/README.md) | React 19, Vite 8, Tailwind CSS 3, Leaflet |
| Mobile app | `mobile/` | Expo SDK 57, React Native 0.86, TypeScript |
| Smart contract | `backend/contracts/` | Solidity 0.8.20 on Ganache 7 |

Current component-by-component status, including known gaps: **[docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)**.

---

## Quick start

```bash
# 1. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # set SECRET_KEY
python seed_data.py                # demo accounts (password Demo@123)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
#   API docs: http://localhost:8000/docs

# 2. (optional) Local blockchain, in another terminal
npx ganache@7.9.2 --wallet.deterministic --chain.chainId 1337
cd backend && python scripts/deploy_contract.py

# 3. Web app
cd frontend && npm ci && npm run dev   # http://localhost:5174

# 4. Mobile app (Expo Go on a phone on the same Wi-Fi)
cd mobile && npm ci && npx expo start
```

The mobile app finds the backend automatically at `http://<IP of the computer running Expo>:8000/api`. To override it, set `EXPO_PUBLIC_API_URL` in `mobile/.env` (see `mobile/.env.example`). The Android emulator falls back to `10.0.2.2`, and the iOS simulator and web fall back to `localhost`. Start uvicorn with `--host 0.0.0.0` so the phone can reach it.

Demo accounts: `farmer@agrocarbon.demo`, `buyer@ecocorp.demo`, `auditor@agrocarbon.demo`, `admin@agrocarbon.demo` (plus `farmer2@…`, `buyer2@…`), all `Demo@123`.

---

## How it works

```
Farmer registers plot (boundary + area)                     status SUBMITTED, verification PENDING
   └─ submits ground photo + soil SOC (+ optional reported NDVI)
        └─ Verification run
             NDVI   ← Sentinel-2 B04/B08 pixels over the plot   (or reported value + source + date)
             CV     ← MobileNetV3 ground-photo classifier
             SOC    ← soil test value, benchmarked
             Score = 0.40·NDVI + 0.35·CV + 0.25·SOC
             ≥75 APPROVED · ≥55 REVIEW · <55 REJECTED · any modality missing → PENDING
             HIGH fraud risk or reported NDVI → at most REVIEW (auditor must confirm)
        └─ Auditor may approve / keep in review / reject (notes required to override)
             └─ APPROVED → credit lot minted (tCO2e = trees × 0.05 × species × practice factors)
                  └─ recorded on CarbonCreditRegistry (if Ganache is up) → listed in marketplace
                       └─ Buyer purchases (whole lot) → ownership transferred → buyer retires
```

### Evidence integrity rules

- No value is ever invented. A missing photo, soil value or NDVI keeps the plot **PENDING**, the API returns `null`, and the apps show "—".
- NDVI provenance is recorded on every verification: `SENTINEL2_COMPUTED` (pixels actually read), `REPORTED` (farmer-supplied, needs an auditor), or none (unavailable).
- Every decision stores its reasons and an evidence snapshot (inputs and the photo's SHA-256), so it can be audited later.
- The marketplace lists a credit only if it is AVAILABLE, its plantation is VERIFIED, and it came from the plantation's latest APPROVED, fully scored verification with recorded NDVI provenance. Otherwise it is neither listed nor purchasable.
- Blockchain hashes are shown only if a transaction was actually mined. Otherwise the status is `NOT_RECORDED`.

### Fraud / risk checks (`backend/app/services/risk_engine.py`)

These checks add up to a 0–100 risk score: reused photo (perceptual hash), non-plantation or unclear photo, satellite vs. photo disagreement, implausible tree density, implausible SOC, and overlapping coordinates. HIGH (≥ 61) downgrades APPROVED to REVIEW.

---

## Tests

```bash
cd backend && pytest                       # 79 tests; real-chain tests run if Ganache is on :8545
cd frontend && npm run build && npm run lint
cd mobile && npx tsc --noEmit && npx expo export --platform android
```

---

## Limitations

- **Ground-photo model**: trained and validated only on procedurally generated synthetic images (`backend/ml/prepare_dataset.py`). Its recorded 100% validation accuracy is on that synthetic data and says nothing about real photographs. It needs retraining on real field photos before its scores mean anything.
- **Satellite NDVI**: computed from Sentinel-2 L2A over a square with the plot's area around its centroid (the drawn polygon is not stored by the backend). Pixels are not cloud-masked beyond the scene-level cloud filter (< 20%). This path needs internet access to Microsoft Planetary Computer, and it has not been exercised against the live service in the automated tests.
- **Carbon quantity**: a flat per-tree assumption with species and practice multipliers. It is not an allometric or registry methodology.
- **Blockchain**: local Ganache only. Users have custodial demo addresses and the backend signs every transaction.
- **Payments**: none; purchases are recorded as prototype transactions.
