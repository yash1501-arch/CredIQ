# CredIQ — How to Run (Local Demo)

## Prerequisites
- **PostgreSQL 16** (local, Docker, or cloud — Supabase/Neon/Railway)
- **Python 3.11+** (venv recommended)
- **Node.js 20+**

---

## 1. Configure Database
```bash
cp .env.example .env
# Edit .env → set DATABASE_URL=postgresql://user:pass@host:5432/crediq
```

---

## 2. Generate Synthetic Data & Train Model (one-time)
```bash
cd ml-service
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

python synthetic_data/generate_synthetic_data.py   # ~3k borrowers, correlated signals
python features/feature_engineering.py             # → feature_store.json + training_features.json
python training/train_model.py                     # prints per-segment AUC table
# → artifacts saved to ml-service/artifacts/
```

---

## 3. Start ML Microservice (FastAPI)
```bash
# In ml-service/ with venv active
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Health check: curl http://localhost:8000/health
```

---

## 4. Seed Database & Start Orchestration API (Express + Prisma)
```bash
# Back to project root
cd ..
npm install
npx prisma generate
npx prisma migrate dev --name init
npx prisma db seed          # loads synthetic JSON into Postgres
npm run dev                 # API on http://localhost:3000
# Health check: curl http://localhost:3000/health
```

---

## 5. Start Dashboard (React + Vite + Tailwind)
```bash
cd dashboard
npm install
npm run dev                 # http://localhost:5173 (or 5174)
```

---

## 6. Test the Demo
1. Open **http://localhost:5173**
2. Click **Search** with a borrower ID from seeded data (e.g., copy one from `ml-service/synthetic_data/data/borrowers.json`)
3. See: Risk Score (0–100), Risk Band (LOW/MEDIUM/HIGH/CRITICAL), Probability of Default, **Top 5 SHAP drivers in plain English**
4. Portfolio heatmap shows risk concentration by sector × loan type

---

## Quick API Tests
```bash
# ML service
curl http://localhost:8000/health
curl -X POST http://localhost:8000/explain -H "Content-Type: application/json" -d '{"borrowerId":"test","loanType":"PERSONAL","gstDelayAvgDays":10,"gstOnTimeRatio":0.8,"upiVolatilityIndex":1.1,"epfoConsistencyRatio":0.9,"debtToIncomeProxy":0.5,"utilizationTrend":0.3,"creditScore":750,"delinquencies12m":0}'

# Express API
curl http://localhost:3000/health
curl http://localhost:3000/api/portfolio/summary
curl "http://localhost:3000/api/borrowers/search?q=<name>"
```

---

## Docker Compose (all services except dashboard)
```bash
docker-compose up --build
# Starts: Postgres (5432), ML service (8000), Express API (3000)
# Run dashboard still run dashboard separately: cd dashboard && npm run dev
```

---

## Key Files for Judges
| What | Where |
|------|-------|
| Model metrics (AUC table) | `ml-service/training/train_model.py` output |
| SHAP explainability | `ml-service/app/main.py` → `/explain` endpoint |
| Segment-aware heads | `ml-service/training/train_model.py` (per-loan-type XGBoost) |
| Feature framework | `ml-service/features/feature_engineering.py` |
| Synthetic data correlations | `ml-service/synthetic_data/generate_synthetic_data.py` |
| Dashboard UI | `dashboard/src/App.tsx` |
| Architecture docs | `docs/` (PRD, SAD, Schema) |