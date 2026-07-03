# CredIQ — IDBI Innovate 2026 Track 04
**Predictive AI for MSME Credit Risk & Early Warning**

Solo MVP built for hackathon submission. End-to-end pipeline:
1. **Synthetic data generator** (Python) — correlated borrower/loan/GST/UPI/EPFO/bureau records
2. **Feature engineering** — filing regularity, UPI volatility, EPFO consistency, DTI, utilization
3. **Segment-aware XGBoost** — one shared feature framework, per-loan-type heads (Personal, Home, Mortgage, Auto)
4. **SHAP explainability** — top-5 plain-English drivers per prediction
5. **FastAPI ML service** — `/predict`, `/explain`, `/model-metrics`
6. **Express + Prisma orchestration API** — persistence, borrower search, portfolio heatmap
7. **React (Vite) dashboard** — borrower search, risk score + band, SHAP driver panel, portfolio heatmap

---

## Quick Start (Local)

### Prerequisites
- Python 3.11+ (venv recommended)
- Node.js 20+
- **PostgreSQL 16** (local or cloud — e.g., Supabase, Neon, Railway)
- Docker (optional, for docker-compose)

### 1. Clone & Configure
```bash
git clone <repo>
cd CredIQ

# Copy env template and edit DATABASE_URL
cp .env.example .env
# Edit .env with your Postgres connection string
```

### 2. Generate Synthetic Data & Train Model
```bash
cd ml-service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Generate ~3k borrowers with correlated risk signals
python synthetic_data/generate_synthetic_data.py

# Engineer features → feature_store.json
python features/feature_engineering.py

# Train XGBoost models (4 segments) + SHAP explainers
python training/train_model.py
# → Prints AUC/Accuracy/Precision/Recall per segment
# → Saves artifacts/ml_artifacts.pkl
```

### 3. Start ML Microservice (FastAPI)
```bash
cd ml-service
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Health: http://localhost:8000/health
```

### 4. Seed Database & Start Orchestration API (Express)
```bash
cd ..
npm install
npx prisma generate
npx prisma migrate dev --name init
npx prisma db seed  # loads synthetic data into Postgres
npm run dev
# API: http://localhost:3000
```

### 5. Start Dashboard (React + Vite)
```bash
cd dashboard
npm install
npm run dev
# Dashboard: http://localhost:5173
```

---

## Docker Compose (All-in-One)
```bash
# Requires Docker Desktop
docker-compose up --build
# Starts: Postgres (5432), ML service (8000), Express API (3000)
# Frontend runs separately: cd dashboard && npm run dev
```

---

## Key Endpoints

| Service | Method | Endpoint | Description |
|---------|--------|----------|-------------|
| ML (FastAPI) | GET | `/health` | Service health + model version |
| ML | GET | `/model-metrics` | Per-segment AUC/Acc/Prec/Rec |
| ML | POST | `/explain` | Single prediction + SHAP drivers |
| ML | POST | `/predict` | Batch predictions |
| Express | POST | `/api/borrowers/:id/score` | Score + persist risk score |
| Express | GET | `/api/borrowers/:id/risk` | Latest score + explanations |
| Express | GET | `/api/portfolio/summary` | Heatmap aggregates |
| Express | GET | `/api/borrowers/search?q=` | Search by name/sector |
| Express | GET | `/api/loans/:loanType/model-metrics` | Segment metrics |

---

## Synthetic vs. Real Sandbox Data

| Synthetic Table | Real Sandbox Source (Post-Shortlist) |
|-----------------|--------------------------------------|
| `GstFiling` | GSTN filing API |
| `UpiTransaction` | UPI pattern sandbox |
| `EpfoContribution` | EPFO records sandbox |
| `BureauRecord` | Credit bureau sandbox |

All schema fields mirror expected sandbox payloads 1:1. Swapping the generator for real connectors is a data-loading change only — no schema or API redesign needed.

---

## Model Evaluation (Current Synthetic Run)

```
Model run ID: <UUID>
Version: v1-<timestamp>
Feature set: gstDelayAvgDays, gstOnTimeRatio, upiVolatilityIndex,
             epfoConsistencyRatio, debtToIncomeProxy, utilizationTrend,
             creditScore, delinquencies12m

  PERSONAL   | AUC=0.75  Acc=0.66  Prec=0.78  Rec=0.69
  HOME       | AUC=0.79  Acc=0.70  Prec=0.69  Rec=0.68
  MORTGAGE   | AUC=0.75  Acc=0.70  Prec=0.71  Rec=0.63
  AUTO       | AUC=0.77  Acc=0.70  Prec=0.78  Rec=0.68
============================================================
Weighted AUC-ROC across segments: ~0.76
```

> **Note:** AUC ~0.76 on fully synthetic data with strong injected signal. With real sandbox data and more training time, target ≥0.85 is realistic. The framework (shared features + segment heads + SHAP) is production-ready.

---

## Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                │
│  Synthetic Generator → Postgres (raw + feature tables)           │
│  (borrowers, loans, GST, UPI, EPFO, bureau)                      │
└───────────────────────────────┬───────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────┐
│                    FEATURE ENGINEERING (Python)                   │
│  Filing regularity, UPI volatility, EPFO consistency, DTI, etc.  │
│  → feature_store table                                            │
└───────────────────────────────┬───────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────┐
│                  MODEL TRAINING & SERVING (Python)                │
│  XGBoost ensemble (per loan-type segment head)                    │
│  + SHAP TreeExplainer                                             │
│  Exposed via FastAPI: /predict  /explain  /model-metrics         │
└───────────────────────────────┬───────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────┐
│           BACKEND ORCHESTRATION API (Node/Express/TS)             │
│  Auth-light gateway, request validation, Prisma → Postgres        │
│  Calls ML service, persists risk_scores + explanations            │
└───────────────────────────────┬───────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────┐
│                     DASHBOARD (React/Vite/Tailwind)               │
│  Borrower search · Risk score & band · SHAP driver panel          │
│  Portfolio stress heatmap · Trend view                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure
```
CredIQ/
├── .env.example
├── docker-compose.yml
├── package.json              # Express API + Prisma
├── tsconfig.json
├── prisma/
│   ├── schema.prisma         # Full schema per SAD
│   └── seed.ts               # Loads synthetic JSON into Postgres
├── src/
│   └── index.ts              # Express routes per SAD
├── ml-service/
│   ├── requirements.txt
│   ├── synthetic_data/
│   │   ├── generate_synthetic_data.py
│   │   └── data/             # Generated JSON files
│   ├── features/
│   │   └── feature_engineering.py
│   ├── training/
│   │   └── train_model.py
│   ├── artifacts/            # Pickled models + SHAP explainers
│   └── app/
│       └── main.py           # FastAPI endpoints
└── dashboard/
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    └── src/
        ├── main.tsx
        ├── App.tsx
        └── index.css
```

---

## Pitch-Ready Talking Points

- **Single framework, four segments:** Shared feature engineering + per-loan-type XGBoost heads satisfies "common interpretation framework" track requirement.
- **Explainability-first:** Every score ships with 5 plain-English SHAP drivers (e.g., "Credit utilization trend increased risk by 12 points").
- **Synthetic → Real pipeline:** Data generator correlates signals (poor GST → high UPI volatility → higher default prob) so demo is realistic. Swapping generator for real sandbox APIs = data loading change only.
- **Model traceability:** Every `RiskScore` links to a `ModelRun` (version, metrics, trained_at) — full audit trail.
- **Sub-500ms API:** FastAPI + XGBoost inference ~20ms; Express orchestration adds minimal overhead.
- **Portfolio view:** Heatmap by sector × loan type gives risk managers instant stress concentration visibility.

---

## License
MIT — Hackathon MVP. Synthetic data only; no PII.