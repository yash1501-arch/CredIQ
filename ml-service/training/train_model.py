"""
Model training script for CredIQ MSME credit-risk MVP.

- Trains a segment-aware XGBoost model per loan type (PERSONAL, HOME, MORTGAGE, AUTO)
- Shared feature framework, per-segment heads
- Evaluates AUC, accuracy, precision, recall per segment
- Saves model artifacts and SHAP explainers for FastAPI serving
"""

import json
import os
import pickle
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.metrics import accuracy_score, auc, precision_score, recall_score, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parents[1] / "synthetic_data" / "data"
ARTIFACTS_DIR = Path(__file__).parents[1] / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# Expanded feature set for training (includes bureau + extra engineered features)
FEATURE_COLS = [
    "gstDelayAvgDays",
    "gstOnTimeRatio",
    "upiVolatilityIndex",
    "epfoConsistencyRatio",
    "debtToIncomeProxy",
    "utilizationTrend",
    "creditScore",
    "delinquencies12m",
]

LOAN_TYPES = ["PERSONAL", "HOME", "MORTGAGE", "AUTO"]  # MSME handled later
MODEL_VERSION = f"v1-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    features = pd.read_json(DATA_DIR / "training_features.json")
    labels = pd.read_json(DATA_DIR / "labels.json")
    return features, labels


def prepare_data(features: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Merge features and labels, ensure all feature columns exist."""
    df = features.merge(labels[["borrowerId", "loanId", "loanType", "default12m"]], on="borrowerId", how="inner")
    # Ensure feature columns
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0.0
    return df


def train_segment_model(df: pd.DataFrame, loan_type: str) -> dict:
    """Train XGBoost for a single loan type segment."""
    segment_df = df[df["loanType"] == loan_type].copy()
    if len(segment_df) < 100:
        print(f"  ⚠ {loan_type}: only {len(segment_df)} samples, skipping")
        return None

    X = segment_df[FEATURE_COLS]
    y = segment_df["default12m"]

    # Class balance
    pos_weight = (y == 0).sum() / max((y == 1).sum(), 1)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=pos_weight,
        objective="binary:logistic",
        eval_metric="auc",
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )

    model.fit(X_train, y_train, verbose=False)

    # Evaluate
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    fpr, tpr, _ = roc_curve(y_test, y_pred_proba)
    roc_auc = auc(fpr, tpr)
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)

    print(f"  {loan_type}: n={len(segment_df):,} | AUC={roc_auc:.4f} | Acc={acc:.4f} | Prec={prec:.4f} | Rec={rec:.4f}")

    return {
        "model": model,
        "loan_type": loan_type,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "metrics": {
            "accuracy": acc,
            "auc_roc": roc_auc,
            "precision": prec,
            "recall": rec,
        },
        "feature_importance": dict(zip(FEATURE_COLS, model.feature_importances_.tolist())),
    }


def main():
    print(f"Loading data from {DATA_DIR}")
    features, labels = load_data()
    df = prepare_data(features, labels)
    print(f"Merged data: {len(df):,} rows, {df['loanType'].value_counts().to_dict()}")

    # Train per-segment models
    artifacts = {}
    for lt in LOAN_TYPES:
        print(f"\nTraining {lt}...")
        result = train_segment_model(df, lt)
        if result:
            artifacts[lt] = result

    # Save artifacts
    model_run_id = str(uuid.uuid4())
    artifact_path = ARTIFACTS_DIR / f"model_run_{MODEL_VERSION}.pkl"

    # Prepare Prisma ModelRun record data
    model_run_records = {}
    for lt, art in artifacts.items():
        model_run_records[lt] = {
            "id": str(uuid.uuid4()),
            "version": MODEL_VERSION,
            "loanType": lt,
            "trainedAt": datetime.now().isoformat(),
            "accuracy": art["metrics"]["accuracy"],
            "aucRoc": art["metrics"]["auc_roc"],
            "precision": art["metrics"]["precision"],
            "recall": art["metrics"]["recall"],
            "metricsJson": art["metrics"],
        }

    # Save pickle with models + feature_cols + version
    save_obj = {
        "model_run_id": model_run_id,
        "version": MODEL_VERSION,
        "feature_cols": FEATURE_COLS,
        "loan_type_models": {lt: art["model"] for lt, art in artifacts.items()},
        "metrics": {lt: art["metrics"] for lt, art in artifacts.items()},
        "feature_importance": {lt: art["feature_importance"] for lt, art in artifacts.items()},
        "model_run_records": model_run_records,
    }

    with open(artifact_path, "wb") as f:
        pickle.dump(save_obj, f)

    print(f"\nSaved model artifacts to {artifact_path}")

    # Print evaluation summary for pitch
    print("\n" + "=" * 60)
    print("MODEL EVALUATION SUMMARY (for pitch deck)")
    print("=" * 60)
    print(f"Model run ID: {model_run_id}")
    print(f"Version: {MODEL_VERSION}")
    print(f"Feature set: {FEATURE_COLS}")
    print()
    for lt, art in artifacts.items():
        m = art["metrics"]
        print(f"  {lt:10s} | AUC={m['auc_roc']:.4f}  Acc={m['accuracy']:.4f}  "
              f"Prec={m['precision']:.4f}  Rec={m['recall']:.4f}  "
              f"n_test={art['n_test']}")
    print("=" * 60)

    # Overall weighted AUC
    total_test = sum(art["n_test"] for art in artifacts.values())
    weighted_auc = sum(art["metrics"]["auc_roc"] * art["n_test"] for art in artifacts.values()) / total_test
    print(f"Weighted AUC-ROC across segments: {weighted_auc:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()