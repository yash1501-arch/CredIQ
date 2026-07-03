"""
FastAPI ML microservice for CredIQ credit-risk predictions.

Endpoints:
- POST /predict - score a borrower (or batch)
- POST /explain - get SHAP explanations for predictions
- GET /health - health check
- GET /model-metrics - evaluation metrics per segment
"""

import json
import os
import pickle
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Config & model loading
# ---------------------------------------------------------------------------
ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"
MODEL_FILE = None

# Find latest model artifact
for f in sorted(ARTIFACTS_DIR.glob("model_run_*.pkl"), reverse=True):
    MODEL_FILE = f
    break

if MODEL_FILE is None:
    raise RuntimeError(f"No model artifacts found in {ARTIFACTS_DIR}")

with open(MODEL_FILE, "rb") as f:
    artifact = pickle.load(f)

MODELS: Dict[str, xgb.XGBClassifier] = artifact["loan_type_models"]
FEATURE_COLS: List[str] = artifact["feature_cols"]
MODEL_VERSION: str = artifact["version"]
MODEL_RUN_ID: str = artifact["model_run_id"]
METRICS: Dict = artifact["metrics"]
FEATURE_IMPORTANCE: Dict = artifact["feature_importance"]

# Pre-create SHAP explainers (one per segment)
EXPLAINERS = {lt: shap.TreeExplainer(model) for lt, model in MODELS.items()}

app = FastAPI(
    title="CredIQ ML Service",
    version="0.1.0",
    description="MSME Credit Risk Prediction with SHAP Explainability",
)

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class FeatureVector(BaseModel):
    borrowerId: str
    loanType: str = Field(pattern="^(PERSONAL|HOME|MORTGAGE|AUTO|MSME)$")
    gstDelayAvgDays: float
    gstOnTimeRatio: float
    upiVolatilityIndex: float
    epfoConsistencyRatio: float
    debtToIncomeProxy: float
    utilizationTrend: float
    creditScore: int
    delinquencies12m: int


class PredictRequest(BaseModel):
    features: List[FeatureVector]


class SHAPDriver(BaseModel):
    feature: str
    shapValue: float
    direction: str  # "increases_risk" / "decreases_risk"
    plainEnglish: str


class PredictionResponse(BaseModel):
    borrowerId: str
    loanType: str
    probDefault: float
    score0to100: int
    riskBand: str
    modelRunId: str
    modelVersion: str
    shapDrivers: List[SHAPDriver]
    computedAt: str


class ExplainResponse(BaseModel):
    borrowerId: str
    loanType: str
    probDefault: float
    score0to100: int
    riskBand: str
    modelRunId: str
    modelVersion: str
    shapDrivers: List[SHAPDriver]
    featureValues: Dict[str, float]
    computedAt: str


class MetricsResponse(BaseModel):
    modelRunId: str
    modelVersion: str
    segments: Dict[str, Dict[str, float]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
RISK_BANDS = {
    "LOW": (0, 25),
    "MEDIUM": (25, 50),
    "HIGH": (50, 75),
    "CRITICAL": (75, 101),
}

PLAIN_ENGLISH_MAP = {
    "gstDelayAvgDays": "Average GST filing delay",
    "gstOnTimeRatio": "GST on-time filing rate",
    "upiVolatilityIndex": "UPI transaction volatility",
    "epfoConsistencyRatio": "EPFO contribution consistency",
    "debtToIncomeProxy": "Debt-to-income proxy",
    "utilizationTrend": "Credit utilization trend",
    "creditScore": "Bureau credit score",
    "delinquencies12m": "12-month delinquencies",
}


def score_to_band(score: int) -> str:
    for band, (lo, hi) in RISK_BANDS.items():
        if lo <= score < hi:
            return band
    return "CRITICAL"


def plain_english_driver(feature: str, shap_val: float) -> str:
    base = PLAIN_ENGLISH_MAP.get(feature, feature)
    if shap_val > 0:
        return f"{base} increased risk by {abs(shap_val)*100:.1f} points"
    else:
        return f"{base} decreased risk by {abs(shap_val)*100:.1f} points"


def compute_shap_drivers(
    explainer: shap.TreeExplainer, X: np.ndarray, feature_names: List[str], top_k: int = 5
) -> List[SHAPDriver]:
    """Get top-K SHAP drivers in plain English."""
    shap_values = explainer.shap_values(X)
    # For binary classification, shap_values is list of [class_0, class_1] or array (n_samples, n_features)
    if isinstance(shap_values, list):
        shap_vals = shap_values[1][0]  # class 1 (default), first sample
    else:
        shap_vals = shap_values[0]

    # Sort by absolute magnitude
    idx = np.argsort(np.abs(shap_vals))[::-1][:top_k]
    drivers = []
    for i in idx:
        val = float(shap_vals[i])
        drivers.append(SHAPDriver(
            feature=feature_names[i],
            shapValue=val,
            direction="increases_risk" if val > 0 else "decreases_risk",
            plainEnglish=plain_english_driver(feature_names[i], val),
        ))
    return drivers


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_version": MODEL_VERSION,
        "model_run_id": MODEL_RUN_ID,
        "segments": list(MODELS.keys()),
    }


@app.get("/model-metrics", response_model=MetricsResponse)
async def model_metrics():
    return MetricsResponse(
        modelRunId=MODEL_RUN_ID,
        modelVersion=MODEL_VERSION,
        segments=METRICS,
    )


@app.post("/predict", response_model=List[PredictionResponse])
async def predict(request: PredictRequest):
    results = []
    for fv in request.features:
        lt = fv.loanType
        if lt not in MODELS:
            raise HTTPException(status_code=400, detail=f"No model for loan type {lt}")

        # Build feature array in correct order
        row = {col: getattr(fv, col) for col in FEATURE_COLS}
        X = pd.DataFrame([row], columns=FEATURE_COLS)

        model = MODELS[lt]
        prob = float(model.predict_proba(X)[0, 1])
        score = int(round(prob * 100))
        band = score_to_band(score)

        # SHAP drivers
        explainer = EXPLAINERS[lt]
        drivers = compute_shap_drivers(explainer, X.values, FEATURE_COLS)

        results.append(PredictionResponse(
            borrowerId=fv.borrowerId,
            loanType=lt,
            probDefault=prob,
            score0to100=score,
            riskBand=band,
            modelRunId=MODEL_RUN_ID,
            modelVersion=MODEL_VERSION,
            shapDrivers=drivers,
            computedAt=datetime.utcnow().isoformat(),
        ))

    return results


@app.post("/explain", response_model=ExplainResponse)
async def explain(fv: FeatureVector):
    """Same as predict but with full feature values for UI."""
    lt = fv.loanType
    if lt not in MODELS:
        raise HTTPException(status_code=400, detail=f"No model for loan type {lt}")

    row = {col: getattr(fv, col) for col in FEATURE_COLS}
    X = pd.DataFrame([row], columns=FEATURE_COLS)

    model = MODELS[lt]
    prob = float(model.predict_proba(X)[0, 1])
    score = int(round(prob * 100))
    band = score_to_band(score)

    explainer = EXPLAINERS[lt]
    drivers = compute_shap_drivers(explainer, X.values, FEATURE_COLS)

    return ExplainResponse(
        borrowerId=fv.borrowerId,
        loanType=lt,
        probDefault=prob,
        score0to100=score,
        riskBand=band,
        modelRunId=MODEL_RUN_ID,
        modelVersion=MODEL_VERSION,
        shapDrivers=drivers,
        featureValues=row,
        computedAt=datetime.utcnow().isoformat(),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)