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

**Port already in use / "Cannot reach the backend" / `{"detail":"Not Found"}` on `/api/health`?** Another program (often another FastAPI or Docker project) is using port 8000. Run the backend on a free port and point the web app at it:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8765          # backend
echo VITE_API_BASE_URL=http://localhost:8765 > frontend/.env.local   # then restart: npm run dev
```

Check http://localhost:8765/api/health shows `{"status":"healthy","service":"carbon-credit-backend"}`. If `npm run dev` says port 5174 is in use, run `npm run dev -- --port 5175`. Keep the backend and the web app in **separate** terminal windows. The verification step downloads a live Sentinel-2 image and takes about a minute.

The mobile app finds the backend automatically at `http://<IP of the computer running Expo>:8000/api`. To override it, set `EXPO_PUBLIC_API_URL` in `mobile/.env` (see `mobile/.env.example`). The Android emulator falls back to `10.0.2.2`, and the iOS simulator and web fall back to `localhost`. Start uvicorn with `--host 0.0.0.0` so the phone can reach it.

Demo accounts: `farmer@agrocarbon.demo`, `buyer@ecocorp.demo`, `auditor@agrocarbon.demo`, `admin@agrocarbon.demo` (plus `farmer2@…`, `buyer2@…`), all `Demo@123`. Sign in from the landing page portal cards (Farmer / Buyer / Auditor). Anyone can sign up as a farmer, buyer or auditor; the admin signs in through the Auditor portal. An admin can also create auditor accounts (Admin dashboard → "Create auditor account").

### Deploying (web on Vercel, backend on Render)

The backend cannot run on Vercel: PyTorch and rasterio exceed its function size limit, its filesystem does not keep the SQLite database or uploaded photos, and a satellite verification takes about a minute.

1. **Backend on Render.** New → Blueprint → pick this repo; `render.yaml` sets everything up (CPU-only PyTorch, a 1 GB disk at `/var/data` for the database and photos, a generated `SECRET_KEY`). Enter `CORS_ORIGINS` when asked (use `*` until the Vercel URL exists, then change it). After the first deploy, open the service's Shell and run `python seed_data.py` once to create the demo accounts. Check `https://<service>.onrender.com/api/health`.
2. **Web app on Vercel.** Add New → Project → import this repo. Root Directory `frontend`, Framework Vite, environment variable `VITE_API_BASE_URL=https://<service>.onrender.com`. Deploy, then set Render's `CORS_ORIGINS` to the Vercel URL.
3. **Android APK**: see below, using `https://<service>.onrender.com/api`.

### Free option: backend on your laptop through an ngrok tunnel

Keeps the real database and photos on the laptop; the site and app work while the laptop, the backend and the tunnel are running. ngrok's free plan gives one fixed `https://<name>.ngrok-free.app` address (about 20k requests a month). The web app and mobile app send the `ngrok-skip-browser-warning` header on every request, including photo loads, so ngrok's browser warning page never gets in the way.

```bash
# terminal 1
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8765
# terminal 2 (after installing ngrok and adding your authtoken)
ngrok http --url=https://<your-dev-domain>.ngrok-free.app 8765
```

Use `https://<your-dev-domain>.ngrok-free.app` as `VITE_API_BASE_URL` on Vercel and `https://<your-dev-domain>.ngrok-free.app/api` as `EXPO_PUBLIC_API_URL` for the APK.

### Android APK

Built in the cloud with EAS (free Expo account; no Android Studio needed). The backend URL is baked in at build time, so deploy the backend first and use its **https** address (release builds block plain `http://`).

```bash
cd mobile
npm install -g eas-cli
eas login
eas build -p android --profile preview      # first run: answer "yes" to create the project and keystore
```

Before building, set the backend URL in `mobile/eas.json` under the `preview` profile (a local `.env` is git-ignored and is not uploaded to the build server):

```json
"preview": { "distribution": "internal", "android": { "buildType": "apk" },
             "env": { "EXPO_PUBLIC_API_URL": "https://<your-backend-host>/api" } }
```

When the build finishes (about 10–20 minutes) EAS prints a download link and QR code for the `.apk`. Install it on a phone (allow "install unknown apps"). Rebuild whenever the backend URL changes; bump `android.versionCode` in `app.json` for each new APK you hand out. `--profile production` makes a Play Store `.aab` instead.

---

## How it works

```
Farmer registers plot (boundary + area)                     status SUBMITTED, verification PENDING
   └─ submits ground photos (1–10) + soil SOC (+ optional reported NDVI)
        └─ Verification run
             NDVI   ← cloud-free Sentinel-2 B04/B08 pixels inside the drawn boundary   (or reported value + source + date)
             CV     ← MobileNetV3 classifier on each photo → lower median of unique photos
             SOC    ← soil test value, benchmarked
             Score = 0.40·NDVI + 0.35·CV + 0.25·SOC
             ≥75 APPROVED · ≥55 REVIEW · <55 REJECTED · any modality missing → PENDING
             HIGH fraud risk, reported NDVI, or conflicting / low-confidence photos → at most REVIEW
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
cd backend && pytest                       # 88 tests; real-chain tests run if Ganache is on :8545
cd frontend && npm run build && npm run lint
cd mobile && npx tsc --noEmit && npx expo export --platform android
```

---

## Limitations

- **Ground-photo model (v2)**: trained on ~6,100 real photographs (Intel Image Classification dataset) and scored 98.4% on 1,420 held-out real test photos (`backend/ml/reports/evaluation_v2.md`; the old synthetic-trained model scored 49.6% on the same photos). "Plantation" was learned from forest photos because the dataset has no areca, coconut or agroforestry pictures, so accuracy on real plantation field photos is still unmeasured. Rebuild/retrain with `python ml/build_real_dataset.py && python ml/train.py` (~12 minutes on a laptop CPU).
- **Satellite NDVI**: computed from Sentinel-2 L2A pixels inside the drawn boundary polygon (or, for plots registered with only a GPS point, a square of the plot's area around it). Cloud, shadow, cirrus and snow pixels are removed using the scene classification layer. This path needs internet access to Microsoft Planetary Computer; it was checked live on 2026-10-09 (`backend/scripts/check_live_ndvi.py`, see docs/PROJECT_STATUS.md). The automated tests use local GeoTIFF files, not the live service.
- **Carbon quantity**: a flat per-tree assumption with species and practice multipliers. It is not an allometric or registry methodology.
- **Blockchain**: local Ganache only. Users have custodial demo addresses and the backend signs every transaction.
- **Payments**: none; purchases are recorded as prototype transactions.
