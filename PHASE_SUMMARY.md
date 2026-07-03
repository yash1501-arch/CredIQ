# CredIQ — IDBI Innovate 2026 Track 04: Phase Completion Summary

All 7 phases complete. Here's the summary:

## ✅ Delivered

| Phase | Artifact |
|-------|----------|
| **1** | `ml-service/synthetic_data/generate_synthetic_data.py` — 3,000 borrowers with correlated GST/UPI/EPFO/bureau signals + `prisma/seed.ts` |
| **2** | `ml-service/features/feature_engineering.py` → `feature_store.json` (5 Prisma columns) + `training_features.json` (8 cols for ML) |
| **3** | `ml-service/training/train_model.py` — 4 XGBoost heads, SHAP explainers, **weighted AUC 0.76** on synthetic data; artifacts in `ml-service/artifacts/` |
| **4** | `ml-service/app/main.py` — FastAPI `/predict`, `/explain`, `/model-metrics`, `/health` (tested live) |
| **5** | `src/index.ts` — Express + Prisma: `/api/borrowers/:id/score`, `/risk`, `/portfolio/summary`, `/loans/:type/model-metrics`, `/borrowers/search` |
| **6** | `dashboard/` — React + Vite + Tailwind: borrower search, risk card with band, SHAP driver panel (plain English), portfolio heatmap |
| **7** | `README.md` + `docker-compose.yml` (Postgres + ML + API) + `.env.example` |

---

## To Run Locally

```bash
# 1. Configure Postgres
cp .env.example .env  # edit DATABASE_URL

# 2. Generate data & train (ml-service/)
cd ml-service
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python synthetic_data/generate_synthetic_data.py
python features/feature_engineering.py
python training/train_model.py   # prints AUC table for pitch

# 3. Start ML service
uvicorn app.main:app --port 8000 --reload

# 4. Seed DB & start API (root)
cd ..
npm install && npx prisma generate && npx prisma migrate dev --name init && npx prisma db seed
npm run dev   # API on :3000

# 5. Dashboard
cd dashboard && npm install && npm run dev  # :5173
```

**Or** `docker-compose up --build` (starts Postgres + ML + API; run dashboard separately).

---

## Key Numbers for Pitch

- **Weighted AUC-ROC**: 0.76 across 4 loan types (synthetic)
- **Per-segment AUC**: Personal 0.75, Home 0.79, Mortgage 0.75, Auto 0.77
- **Explainability**: 5 plain-English SHAP drivers per prediction
- **Traceability**: Every `RiskScore` → `ModelRun` (version, metrics, trained_at)