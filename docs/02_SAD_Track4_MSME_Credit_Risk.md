# Solution Architecture Document (SAD)
## IDBI Innovate 2026 — Track 04: Predictive AI for MSME Credit Risk & Early Warning

**Author:** Narayan
**Track:** 04
**Document status:** v1.0

---

## 1. Architecture Principles
- **Interface-based data layer** — synthetic data today, real sandbox APIs tomorrow, no redesign
- **Explainability-first** — every prediction ships with its reasoning, not just a number
- **Segment-aware, framework-consistent** — one pipeline, one feature framework, per-segment model heads
- **Solo-buildable** — minimal moving parts, leverage managed/serverless hosting, AI-tool-scaffolded boilerplate

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                │
│  Synthetic Data Generator  →  Postgres (raw + feature tables)     │
│  (borrowers, loans, GST, UPI, EPFO, bureau)                       │
└───────────────────────────────┬───────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────┐
│                    FEATURE ENGINEERING LAYER (Python)              │
│  Filing regularity, UPI volatility, EPFO consistency,               │
│  DTI, utilization ratios → feature_store table                     │
└───────────────────────────────┬───────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────┐
│                  MODEL TRAINING & SERVING (Python)                 │
│  XGBoost/LightGBM ensemble (per loan-type segment head)             │
│  + SHAP explainability layer                                        │
│  Exposed via FastAPI: /predict  /explain  /portfolio-summary       │
└───────────────────────────────┬───────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────┐
│               BACKEND ORCHESTRATION API (Node.js/Express/TS)        │
│  Auth-light gateway, request validation, Prisma → Postgres          │
│  Calls ML service, persists risk_scores + explanations              │
└───────────────────────────────┬───────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────┐
│                     DASHBOARD (React/Next.js)                       │
│  Borrower search · Risk score & band · SHAP driver panel            │
│  Portfolio stress heatmap · Trend view                              │
└─────────────────────────────────────────────────────────────────┘
```

## 3. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Data storage | PostgreSQL | Matches your existing stack; relational fit for structured financial data |
| ORM | Prisma | Already your primary tool; fast schema iteration |
| ML/Data science | Python, pandas, scikit-learn, XGBoost/LightGBM | Best tooling for tabular credit-risk modeling |
| Explainability | SHAP | Industry-standard, directly satisfies the "common interpretation framework" requirement |
| Model serving | FastAPI (Python microservice) | Lightweight, fast to stand up, native to the ML stack |
| Orchestration API | Node.js + Express + TypeScript | Your core stack; handles auth, validation, persistence |
| Frontend | React/Next.js (or Streamlit for speed if solo time is tight) | Dashboard for demo/pitch |
| Synthetic data | Faker + SDV (Synthetic Data Vault) | Realistic correlated alternate-data generation |
| Hosting | Railway/Render (API + Postgres), Vercel (frontend) | Fast, free-tier-friendly solo deployment |
| Dev acceleration | Claude Code / AI coding assistant | Scaffold boilerplate, free up time for model quality |

## 4. Component Breakdown

### 4.1 Data Layer
- Synthetic data generator script produces borrower, loan, GST filing, UPI transaction, and EPFO contribution records with realistic joint distributions (e.g., borrowers with poor GST compliance also show more UPI volatility)
- Loaded into Postgres via Prisma migrations/seed scripts
- Schema explicitly documents which fields map to real IDBI sandbox fields (see Database Schema doc)

### 4.2 Feature Engineering Layer
- Python job computes derived features: GST filing delay average, UPI inflow/outflow volatility, EPFO contribution consistency ratio, debt-to-income proxy, credit utilization trend
- Writes to a `feature_store` table keyed by borrower_id + as-of-date, enabling point-in-time correctness

### 4.3 Model Layer
- Gradient-boosted ensemble (XGBoost or LightGBM) — one shared feature framework, with segment-aware model heads per loan type to preserve "common interpretation framework" while respecting different risk profiles
- SHAP TreeExplainer generates per-prediction feature attributions
- Model artifacts versioned (model_id, trained_at, metrics) and stored for traceability

### 4.4 Orchestration API (Node/Express/TS)
Endpoints:
- `POST /api/borrowers/:id/score` — triggers scoring, persists result
- `GET /api/borrowers/:id/risk` — latest score + explanation
- `GET /api/portfolio/summary` — aggregate stress heatmap data
- `GET /api/loans/:loanType/model-metrics` — accuracy/AUC per segment (for the judging narrative)

### 4.5 Dashboard
- Borrower search → risk score, band, trend line
- "Why this score" panel — top 5 SHAP drivers rendered in plain language
- Portfolio heatmap — risk concentration by sector/loan type

## 5. Data Flow
1. Synthetic generator seeds Postgres
2. Feature engineering job computes `feature_store`
3. Training job trains segment models, evaluates, stores metrics
4. FastAPI serves `/predict` + `/explain` on demand
5. Express API calls FastAPI, persists `risk_scores` + `explanations`, serves dashboard
6. Dashboard renders live via Express API

## 6. Deployment Architecture
- Two lightweight services: `ml-service` (FastAPI, containerized) and `api-service` (Express, containerized), both on Railway/Render
- Postgres managed instance (Railway/Render/Supabase)
- Frontend on Vercel
- CI: simple GitHub Actions build/deploy on push (optional, nice-to-have for judging polish)

## 7. Security & Compliance Notes (for pitch credibility)
- No real PII — synthetic data only, explicitly labeled
- Data layer designed so production deployment would sit inside IDBI's sandbox/VPC, consuming real sandbox APIs through the same interface contract
- Model explainability directly supports RBI's fair-lending / explainable-AI expectations for credit decisioning

## 8. Roadmap Beyond Hackathon (PoC stage)
- Swap synthetic data generator for real GSTN/UPI/AA/EPFO sandbox connectors (same interface, no redesign)
- Add model monitoring/drift detection
- Add RBAC and audit logging for underwriter actions
- Expand to MSME-specific unstructured signals (e.g., invoice text, GST return anomalies via NLP)
