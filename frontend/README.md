# Web frontend — React + Vite

```bash
cd frontend
npm ci
cp .env.example .env        # VITE_API_BASE_URL, default http://localhost:8000
npm run dev                 # http://localhost:5174 (port fixed in vite.config.js)
npm run build               # production build into dist/
npm run lint                # oxlint
```

All data comes from the FastAPI backend (`src/services/api.js`). If the backend is unreachable or returns an error, pages show the error. They do not fall back to sample data.

The Verification Wall (`src/pages/VerificationReportPage.jsx`) shows one plantation's evidence, the three modality scores, the decision reasons, the auditor decision panel and the verification history. Missing numbers are shown as "—".
