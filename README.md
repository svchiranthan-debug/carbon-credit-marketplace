# CARBON CREDIT MARKETPLACE WITH MULTI-MODAL VERIFICATION
> **Final-Year Engineering Project Prototype** • Multi-Modal Remote Sensing (Sentinel-2 STAC), Deep Learning Computer Vision (MobileNetV3), Soil Organic Carbon (SOC), Explainable Risk Engine & Cross-Platform Mobile Application.

---

## 1. Executive Summary & Problem Statement

Smallholder and marginal farmers (managing 1–5 hectares) who adopt agroforestry and regenerative soil practices are overwhelmingly excluded from voluntary carbon markets due to prohibitive validation expenses:
* **Prohibitive Audit Costs**: Physical site inspections and MRV (Measurement, Reporting, and Verification) consultant fees typically range between ₹2,00,000 – ₹5,00,000 per project.
* **Lengthy Certification Timelines**: Traditional audit cycles span 6 to 18 months.
* **Intermediary Extraction**: Up to 70% of credit value is captured by brokers rather than the grassroots cultivators.

### The Multi-Modal Solution
This platform implements an automated, decentralized multi-modal verification architecture combining three independent telemetry signals evaluated through an explainable verification formula, backed by an explainable **Risk & Fraud Detection Engine**:
1. **🛰️ Real Satellite / NDVI Remote Sensing (40%)**: Geospatial vegetation health and canopy density derived from Sentinel-2 L2A STAC APIs querying Red (Band 4) and Near-Infrared (Band 8) spectral reflectance.
2. **📷 AI-Based Ground Plantation Verification (35%)**: PyTorch-trained MobileNetV3-Small deep learning model classifying ground-level evidence into `plantation`, `non_plantation`, or `unclear_evidence` with calibrated confidence scores.
3. **🌱 Soil Organic Carbon (SOC) Scoring (25%)**: Subsurface soil organic carbon percentage benchmarked against regional soil taxonomy and agronomic baselines.

---

## 2. System Architecture

```
                               ┌────────────────────────────────────────────────────────┐
                               │                    CLIENT APPLICATIONS                 │
                               │                                                        │
                               │  Web Application (React 18 + Vite)                     │
                               │  Port: 5174 (Tailwind CSS, MapLibre GL, Lucide)        │
                               │                                                        │
                               │  Mobile Application (React Native + Expo SDK 52)      │
                               │  iOS + Android (Native Camera, GPS Location, REST API) │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ JSON REST API (Bearer JWT)
                                                           ▼
                               ┌────────────────────────────────────────────────────────┐
                               │            FASTAPI PYTHON BACKEND (PORT 8000)          │
                               │                                                        │
                               │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
                               │  │ Auth & RBAC  │  │ Plantations  │  │ Transactions │  │
                               │  └──────────────┘  └──────────────┘  └──────────────┘  │
                               │                                                        │
                               │  ┌──────────────────────────────────────────────────┐  │
                               │  │        MULTI-MODAL VERIFICATION PIPELINE         │  │
                               │  │                                                  │  │
                               │  │  1. SATELLITE CLIENT (Sentinel-2 STAC L2A)       │  │
                               │  │     Bands: B04 (Red 665nm) + B08 (NIR 842nm)     │  │
                               │  │     NDVI = (NIR - Red) / (NIR + Red)             │  │
                               │  │                                                  │  │
                               │  │  2. AI VISION SERVICE (PyTorch MobileNetV3)      │  │
                               │  │     Classes: Plantation, Non-Plantation, Unclear │  │
                               │  │     Fine-tuned on Apple Silicon MPS/CUDA         │  │
                               │  │                                                  │  │
                               │  │  3. SOIL ORGANIC CARBON (SOC) SERVICE            │  │
                               │  │     Agronomic baseline benchmarking              │  │
                               │  │                                                  │  │
                               │  │  Verification Score = 0.40(NDVI)+0.35(CV)+0.25(SOC)
                               │  └──────────────────────────┬───────────────────────┘  │
                               │                             ▼                          │
                               │  ┌──────────────────────────────────────────────────┐  │
                               │  │          RISK & FRAUD DETECTION ENGINE           │  │
                               │  │  • Perceptual Image Hashing (pHash deduplication)│  │
                               │  │  • Cross-modality NDVI vs ground photo disparity │  │
                               │  │  • Biological tree density & SOC bounds check    │  │
                               │  │  • Geospatial centroid duplicate detection       │  │
                               │  │  Decision: LOW (0-30) / MED (31-60) / HIGH (61+) │  │
                               │  │  * HIGH RISK automatically routes to Auditor!    │  │
                               │  └──────────────────────────┬───────────────────────┘  │
                               │                             ▼                          │
                               │  ┌──────────────────────────────────────────────────┐  │
                               │  │ CARBON ESTIMATION & BLOCKCHAIN PROVENANCE        │  │
                               │  │  • Allometric carbon sequestration modeling      │  │
                               │  │  • SHA-256 / Web3 blockchain provenance hashes   │  │
                               │  │  • Marketplace minting, trading & retirement     │  │
                               │  └──────────────────────────────────────────────────┘  │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ SQLAlchemy ORM
                                                           ▼
                               ┌────────────────────────────────────────────────────────┐
                               │           SQLITE PERSISTENCE & AUDIT LOGGING           │
                               │  Users, Plantations, Verifications, Credits, AuditLogs │
                               └────────────────────────────────────────────────────────┘
```

---

## 3. Mathematical Verification & Multi-Modal Methodology

### 3.1 Satellite / NDVI Integration
* **Data Source**: Sentinel-2 Level-2A surface reflectance telemetry queried via Planetary Computer / Copernicus STAC APIs.
* **Spectral Calculation**:
  $$\text{NDVI} = \frac{\rho_{\text{NIR}} - \rho_{\text{Red}}}{\rho_{\text{NIR}} + \rho_{\text{Red}}} = \frac{\text{Band 8} - \text{Band 4}}{\text{Band 8} + \text{Band 4}}$$
* **Statistics Extracted**: Mean NDVI, Minimum NDVI, Maximum NDVI, Vegetation Coverage % ($\text{NDVI} \ge 0.40$), cloud cover %, and acquisition timestamp.
* **Honest Provenance Disclosure**:
  - `is_real_satellite: true` $\implies$ Direct Sentinel-2 STAC raster acquisition.
  - `is_real_satellite: false` $\implies$ Clearly stamped as `DEMO/PROTOTYPE DATA` with simulation notice. Never silently substituted.

### 3.2 AI Computer Vision Model
* **Architecture**: Lightweight `MobileNetV3-Small` fine-tuned with transfer learning for edge and mobile feasibility (~6.2 MB weight footprint).
* **Target Classes**:
  1. `plantation`: Verified agroforestry, orchard, or dense canopy foliage.
  2. `non_plantation`: Urban, concrete, asphalt, barren, or manmade architectural structures.
  3. `unclear_evidence`: Overexposed, pitch black, blurry, or camera-obstructed images.
* **Training & Evaluation**:
  - Training script: `backend/ml/train.py`
  - Evaluation script: `backend/ml/evaluate.py`
  - Dataset generator: `backend/ml/prepare_dataset.py`
  - Model weights: `backend/ml/weights/plantation_classifier_v1.pt`
  - Model metadata: `backend/ml/weights/model_metadata.json`
* **Performance Metrics (Measured on Validation Set)**:
  - Overall Accuracy: **100.0%** (synthetic multi-modal benchmarking dataset)
  - Macro Precision: **1.00**, Recall: **1.00**, F1-Score: **1.00**

### 3.3 Composite Verification Formula
The Verification Engine computes a weighted score out of 100:

$$\text{Verification Score} = (0.40 \times \text{NDVI Score}) + (0.35 \times \text{CV Score}) + (0.25 \times \text{SOC Score})$$

#### Decision Rules:
* **Score $\ge 75.0$** $\implies$ **APPROVED**: Eligible for carbon credit generation.
* **$55.0 \le \text{Score} < 75.0$** $\implies$ **REVIEW**: Flagged for manual Auditor inspection.
* **Score $< 55.0$** $\implies$ **REJECTED**: Insufficient biomass or depleted soil health.
* **Missing Evidence** $\implies$ **PENDING**: Unscored until all modalities are uploaded.

---

## 4. Transparent Risk & Fraud Detection Engine

To prevent greenwashing, duplicate submissions, and fraudulent credit minting, every verification runs through an explainable, multi-factor Risk Engine outputting a transparent 0–100 score:

$$\text{Risk Level} = \begin{cases} 
\text{LOW} & 0 \le \text{Score} \le 30 \\
\text{MEDIUM} & 31 \le \text{Score} \le 60 \\
\text{HIGH} & 61 \le \text{Score} \le 100 \implies \text{Forced Escalation to Auditor Review}
\end{cases}$$

### Transparent Risk Factors & Penalties
1. **Perceptual Image Hash Deduplication (+35 pts)**: Computes 64-bit perceptual hashes (`pHash`) across all registered plantations to detect reused photos even after cropping or resizing.
2. **AI Vision Non-Plantation Flag (+40 pts)**: Detected urban or non-vegetative terrain.
3. **Cross-Modality Disparity (+25 to +30 pts)**: Discrepancy between high satellite NDVI ($\ge 0.70$) and barren ground photos ($< 40$), or vice-versa.
4. **Agronomic Density Anomaly (+25 pts)**: Reported tree density exceeding biological carrying capacity ($> 2,500\text{ trees/ha}$) or $(< 20\text{ trees/ha})$.
5. **Soil Organic Carbon Anomaly (+20 pts)**: Reported SOC exceeding regional ceiling ($> 5.5\%$) or exceeding sandy soil retention limits ($> 3.5\%$).
6. **Centroid Coordinate Collision (+30 pts)**: Submissions overlapping existing active plot coordinates.

---

## 5. Mobile Application (React Native + Expo)

A cross-platform mobile client for iOS and Android located in `mobile/` built with React Native and Expo SDK 52.

### Single Unified Backend
The mobile application uses the **exact same FastAPI backend** (`http://<host>:8000`) and shared REST APIs as the web portal—no second backend was created.

### Role Portals
* **🧑‍🌾 Farmer**:
  - GPS-based native plantation coordinate capture.
  - Native camera photo capture & evidence upload.
  - Soil SOC% entry.
  - Real-time multi-modal audit certificate viewer.
  - Carbon credit minting.
* **🏢 Buyer**:
  - Live marketplace browsing of verified credits.
  - 1-click acquisition with transparent provenance inspection.
  - ESG offset portfolio and on-chain credit retirement.
* **🛡️ Auditor**:
  - Verification queue with risk factor warnings.
  - High-risk manual inspection, approval, or rejection.

---

## 6. Technology Stack

* **Backend**: Python 3.12 / 3.13, FastAPI, SQLAlchemy 2.0, SQLite, PyTorch (`torch`, `torchvision`), `imagehash`, Pillow, Pydantic, Python-JOSE (JWT), Pytest.
* **Web Frontend**: React 18, Vite (Port 5174), Tailwind CSS, MapLibre GL, Lucide React icons.
* **Mobile Frontend**: React Native, Expo SDK 52, TypeScript, `expo-image-picker`, `expo-location`.
* **Blockchain Prototype**: Cryptographic SHA-256 transaction hashes and Web3 Ganache RPC provider (`http://localhost:8545`).

---

## 7. Execution Guide

### Port Allocation:
* **Port 5173**: Dedicated to other projects (PROTECTED — NOT TOUCHED).
* **Port 5174**: Carbon Credit Marketplace Web Frontend.
* **Port 8000**: FastAPI Backend & AI Verification Server.

### Step 1: Start Backend Server
```bash
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
* Backend API: `http://localhost:8000`
* Interactive API Documentation (Swagger UI): `http://localhost:8000/docs`

### Step 2: Start Web Application (Port 5174)
```bash
cd frontend
npm run dev
```
* Access: `http://localhost:5174`

### Step 3: Start Mobile Application (Expo)
```bash
cd mobile
npm start
```
* Press `i` for iOS Simulator, `a` for Android Emulator, or scan the QR code with the Expo Go app.

---

## 8. Automated Test Suite

All 24 automated unit, integration, and end-to-end tests pass cleanly:

```bash
cd backend
python3 -m pytest tests/ -v
```

### Verified Test Suites:
1. `tests/test_satellite_integration.py` (3 tests): STAC bounding box geometry, NDVI raster math, honest demo vs real provenance.
2. `tests/test_ai_vision.py` (5 tests): PyTorch MobileNetV3 loading, inference, confidence outputs, invalid image handling, CVService wrapper.
3. `tests/test_risk_engine.py` (3 tests): Low, medium, high risk scoring, pHash detection, explainable risk factor generation.
4. `tests/test_enhanced_multi_modal_e2e.py` (5 tests): Full 10-step lifecycle (Farmer $\to$ Plot $\to$ Upload $\to$ Multi-Modal Verification $\to$ Risk Engine $\to$ Auditor $\to$ Carbon Asset $\to$ Marketplace $\to$ Buyer Acquisition $\to$ On-Chain Retirement).
5. Existing regression suites (`test_auditor_dashboard_access.py`, `test_e2e_journey.py`, `test_full_user_plantation_journey.py`, `test_missing_evidence.py`, `test_verification_and_flow.py`).

---

## 9. Academic Scope, Disclaimers & Limitations

In accordance with academic research and engineering evaluation standards:
* **Prototype MRV**: This system demonstrates the feasibility of automated multi-modal MRV. It is not an officially accredited carbon registry (such as Verra VCS, Gold Standard, or CDM).
* **Satellite Data Notice**: In the absence of live Copernicus Sentinel Hub API credentials, the system gracefully falls back to deterministic simulation clearly labeled as `DEMO/PROTOTYPE DATA`. Real satellite data is never falsely claimed.
* **AI Training Scope**: The deep learning model was fine-tuned on a multi-class synthetic plantation texture and architectural structure benchmark. For commercial deployment, fine-tuning on regional multi-spectral drone and aerial imagery datasets (e.g., DeepGlobe, TreeSatAI) is recommended.
* **Blockchain Scope**: Provenance hashes are generated using cryptographic SHA-256 state hashing and an Ethereum/Ganache prototype ledger. Secondary market smart contracts are not deployed to mainnet.

---
**CARBON CREDIT MARKETPLACE WITH MULTI-MODAL VERIFICATION • 2026**
