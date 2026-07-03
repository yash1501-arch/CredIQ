# Product Requirements Document (PRD)
## IDBI Innovate 2026 — Track 04: Predictive AI for MSME Credit Risk & Early Warning

**Author:** Narayan
**Track:** 04 — MSME Credit, Predictive AI, Risk Management
**Team size:** Solo (AI-tool assisted)
**Document status:** v1.0 — Draft for submission

---

## 1. Problem Statement (from track brief)
IDBI Bank's current MSME credit evaluation relies on structured financial documents alone, producing prediction accuracy in the 16–22% range for identifying stress/default risk. This is fragmented across loan types and borrower segments, with no unified framework for interpretation.

## 2. Objective
Build a predictive system that estimates a borrower's probability of default 12 months in advance, using both structured (bureau, loan, GST filings, EPFO) and unstructured/alternate (UPI transaction behavior, filing patterns) data — with a single, consistent interpretation framework usable across Personal Loan, Home Loan, Mortgage Loan, and Auto Loan portfolios, and extendable to MSME lending.

## 3. Goals & Success Metrics
| Goal | Metric | Target |
|---|---|---|
| Improve default prediction accuracy | Model accuracy / AUC-ROC | ≥90% accuracy (stretch), AUC ≥ 0.85 as realistic MVP benchmark |
| Early warning horizon | Prediction lead time | 12 months ahead of default event |
| Cross-portfolio consistency | Common risk framework | Single scoring pipeline usable across all 4 loan types |
| Explainability | Feature-level attribution | Every score accompanied by top-5 SHAP drivers |
| Usability for underwriters | Dashboard comprehension | Risk band + explanation visible in <10 seconds |

## 4. Target Users
- **Primary:** IDBI Bank credit/risk underwriters and MSME relationship managers (judges will evaluate from this lens)
- **Secondary:** Risk management / portfolio strategy teams reviewing aggregate stress trends

## 5. Scope

### In scope (Hackathon MVP)
- Data pipeline ingesting structured (loan, bureau) + alternate (GST, UPI, EPFO) features, built on synthetic data mirroring the schema IDBI's sandbox will expose
- Feature engineering layer (filing regularity, transaction volatility, contribution consistency, etc.)
- ML model (gradient-boosted ensemble) predicting probability of default
- Explainability layer (SHAP) generating human-readable risk drivers
- REST API serving risk scores + explanations
- Dashboard visualizing risk score, band (Low/Medium/High/Critical), trend, and top drivers per borrower
- Model evaluation report (accuracy, AUC, confusion matrix, precision/recall by loan type)

### Out of scope (for hackathon; roadmap for PoC stage)
- Live integration with real GSTN/UPI/EPFO/AA/ULI/OCEN APIs (only available post-shortlisting)
- Multi-tenant bank-grade auth/RBAC
- Real-time streaming ingestion
- Model retraining automation / MLOps pipeline (documented as future work only)

## 6. Functional Requirements
- **FR1:** System shall ingest borrower profile, loan, and alternate-data records
- **FR2:** System shall engineer features from raw alternate data (e.g., GST filing delay days, UPI inflow/outflow volatility, EPFO contribution consistency ratio)
- **FR3:** System shall train and serve a probability-of-default model per loan-type segment with a shared feature framework
- **FR4:** System shall output a normalized 0–100 risk score and a risk band
- **FR5:** System shall generate SHAP-based explanations for every prediction
- **FR6:** System shall expose predictions via a REST API (`/predict`, `/explain`, `/portfolio-summary`)
- **FR7:** System shall present results in a dashboard: borrower search, risk score, trend, driver breakdown, portfolio-level stress heatmap

## 7. Non-Functional Requirements
- **Performance:** API response <500ms for single-borrower prediction
- **Explainability:** No black-box output — every score must have attached reasoning
- **Portability:** Architecture must allow swapping synthetic data sources for real sandbox APIs without redesign (interface-based data layer)
- **Reliability:** Model versioning — every prediction traceable to a model run ID
- **Security:** No PII in logs; synthetic data only for demo

## 8. Data Requirements
Since real sandbox data is only released to shortlisted teams, the MVP uses:
1. A public credit-risk base dataset (e.g., Give Me Some Credit / LendingClub / an India MSME default dataset) for realistic default patterns
2. A synthetic alternate-data layer generated to match the sandbox's described schema: GST filings, UPI transaction patterns, EPFO contributions — built with rule-based generation + `SDV` (Synthetic Data Vault) for realistic correlations
3. Documented mapping showing how each synthetic field maps 1:1 to the real sandbox field it will be replaced by post-shortlist

## 9. Key User Flow (Dashboard)
1. Underwriter searches/selects a borrower or loan
2. Dashboard shows current risk score, band, and trend over last N months
3. "Why this score" panel shows top 5 SHAP drivers in plain language
4. Portfolio view shows stress heatmap across loan types/segments

## 10. Assumptions & Constraints
- Solo build, AI-coding-tool assisted (Claude Code / similar), limited timeline before submission deadline
- No access to real bank data or APIs at MVP stage
- Model must generalize across 4 loan types with one framework (per track requirement), not 4 separate bespoke models

## 11. Risks & Mitigations
| Risk | Mitigation |
|---|---|
| Synthetic data looks unrealistic to judges | Explicitly document data lineage and 1:1 schema mapping to real sandbox fields |
| 90% accuracy target unrealistic for MVP timeline | Report realistic AUC/accuracy honestly, position as strong baseline with clear path to 90% with real data + more training time |
| Explainability adds scope | Use off-the-shelf SHAP (low engineering cost, high judging payoff) |
| Solo timeline risk | Use AI coding tools to scaffold boilerplate (API, dashboard, schema) so time is spent on model quality and the pitch narrative |

## 12. Success Criteria (aligned to judging)
- Working demo: input a borrower → get score + explanation in real time
- Clear accuracy/AUC improvement story vs. the stated 16–22% baseline
- Single consistent framework demonstrably applied across loan types
- Clean narrative on how the system plugs into IDBI's real sandbox post-shortlisting
