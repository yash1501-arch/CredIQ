"""
Feature engineering for CredIQ.

Reads raw synthetic data JSON, computes engineered features per borrower
as of SNAPSHOT_DATE, and writes feature_store.json for Prisma seeding.
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

SNAPSHOT_DATE = datetime(2025, 12, 31)
DATA_DIR = Path(__file__).parent.parent / "synthetic_data" / "data"


def load_df(name: str) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.json"
    return pd.read_json(path)


def save_df(df: pd.DataFrame, name: str) -> None:
    path = DATA_DIR / f"{name}.json"
    # Prisma expects ISO datetime strings, Decimal as float
    df.to_json(path, orient="records", date_format="iso", double_precision=6)
    print(f"Wrote {name}: {len(df):,} rows -> {path}")


def main() -> None:
    print("Loading raw data...")
    borrowers = load_df("borrowers")
    loans = load_df("loans")
    bureau = load_df("bureau_records")
    gst = load_df("gst_filings")
    upi = load_df("upi_transactions")
    epfo = load_df("epfo_contributions")

    # Ensure datetime columns
    gst["period_dt"] = pd.to_datetime(gst["period"] + "-01")
    epfo["period_dt"] = pd.to_datetime(epfo["period"] + "-01")
    upi["txnDate"] = pd.to_datetime(upi["txnDate"])
    bureau["asOfDate"] = pd.to_datetime(bureau["asOfDate"])

    # -----------------------------------------------------------------------
    # 1. GST: average delay days, on-time ratio, turnover trend
    # -----------------------------------------------------------------------
    gst_recent = gst[gst["period_dt"] <= SNAPSHOT_DATE].copy()
    gst_agg = gst_recent.groupby("borrowerId").agg(
        gstDelayAvgDays=("delayDays", "mean"),
        gstOnTimeRatio=("filedOnTime", "mean"),
        gstTurnoverTrend=("turnover", lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) > 1 else 0.0),
    ).reset_index()

    # -----------------------------------------------------------------------
    # 2. UPI: inflow/outflow volatility index
    #    - daily inflow/outflow volumes and amounts
    #    - compute coefficient of variation of daily net flow
    # -----------------------------------------------------------------------
    upi_recent = upi[upi["txnDate"] <= SNAPSHOT_DATE].copy()
    upi_recent["day"] = upi_recent["txnDate"].dt.date
    daily = upi_recent.groupby(["borrowerId", "day", "direction"])["amount"].sum().unstack(fill_value=0)
    daily = daily.groupby("borrowerId").agg(
        inflow_cv=("inflow", lambda x: x.std() / x.mean() if x.mean() > 0 else 0),
        outflow_cv=("outflow", lambda x: x.std() / x.mean() if x.mean() > 0 else 0),
        net_flow_mean=("inflow", "mean"),
        net_flow_std=("outflow", "std"),
    ).reset_index()
    daily["upiVolatilityIndex"] = np.sqrt(daily["inflow_cv"]**2 + daily["outflow_cv"]**2)
    upi_agg = daily[["borrowerId", "upiVolatilityIndex"]].copy()

    # -----------------------------------------------------------------------
    # 3. EPFO: contribution consistency ratio
    # -----------------------------------------------------------------------
    epfo_recent = epfo[epfo["period_dt"] <= SNAPSHOT_DATE].copy()
    epfo_agg = epfo_recent.groupby("borrowerId").agg(
        epfoConsistencyRatio=("isConsistent", "mean"),
        epfoAvgEmployees=("employeeCount", "mean"),
        epfoAvgContribution=("contribution", "mean"),
    ).reset_index()

    # -----------------------------------------------------------------------
    # 4. Bureau: debt-to-income proxy, utilization trend (snapshot only)
    # -----------------------------------------------------------------------
    # DTI proxy: existingDebt / (estimated_income)
    # estimated_income from GST turnover (annualized)
    gst_turnover_annual = gst_recent.groupby("borrowerId")["turnover"].sum().reset_index()
    gst_turnover_annual.rename(columns={"turnover": "estimatedAnnualTurnover"}, inplace=True)
    bureau_enriched = bureau.merge(gst_turnover_annual, on="borrowerId", how="left")
    bureau_enriched["debtToIncomeProxy"] = (
        bureau_enriched["existingDebt"] / bureau_enriched["estimatedAnnualTurnover"].clip(lower=1)
    ).fillna(0)
    # utilizationTrend: since we only have one snapshot, use utilizationPct directly
    bureau_enriched["utilizationTrend"] = bureau_enriched["utilizationPct"] / 100.0
    bureau_agg = bureau_enriched[["borrowerId", "debtToIncomeProxy", "utilizationTrend", "creditScore", "delinquencies12m"]].copy()

    # -----------------------------------------------------------------------
    # 5. Merge all features
    # -----------------------------------------------------------------------
    features = borrowers[["id"]].rename(columns={"id": "borrowerId"})
    features = features.merge(gst_agg, on="borrowerId", how="left")
    features = features.merge(upi_agg, on="borrowerId", how="left")
    features = features.merge(epfo_agg, on="borrowerId", how="left")
    features = features.merge(bureau_agg, on="borrowerId", how="left")

    # Fill NaN with neutral values
    features["gstDelayAvgDays"] = features["gstDelayAvgDays"].fillna(30.0)
    features["gstOnTimeRatio"] = features["gstOnTimeRatio"].fillna(0.5)
    features["gstTurnoverTrend"] = features["gstTurnoverTrend"].fillna(0.0)
    features["upiVolatilityIndex"] = features["upiVolatilityIndex"].fillna(0.5)
    features["epfoConsistencyRatio"] = features["epfoConsistencyRatio"].fillna(0.7)
    features["debtToIncomeProxy"] = features["debtToIncomeProxy"].fillna(0.5)
    features["utilizationTrend"] = features["utilizationTrend"].fillna(0.3)
    features["creditScore"] = features["creditScore"].fillna(650)
    features["delinquencies12m"] = features["delinquencies12m"].fillna(0)

    # -----------------------------------------------------------------------
    # 6. Build FeatureStore records matching Prisma schema (5 columns only)
    # -----------------------------------------------------------------------
    import uuid
    feature_store = pd.DataFrame({
        "id": [str(uuid.uuid4()) for _ in range(len(features))],
        "borrowerId": features["borrowerId"],
        "asOfDate": SNAPSHOT_DATE.isoformat(),
        "gstDelayAvgDays": features["gstDelayAvgDays"].round(4),
        "upiVolatilityIndex": features["upiVolatilityIndex"].round(4),
        "epfoConsistencyRatio": features["epfoConsistencyRatio"].round(4),
        "debtToIncomeProxy": features["debtToIncomeProxy"].round(4),
        "utilizationTrend": features["utilizationTrend"].round(4),
    })

    # -----------------------------------------------------------------------
    # 7. Also save the full feature table for training (includes extra features)
    # -----------------------------------------------------------------------
    training_features = features.copy()
    training_features.to_json(DATA_DIR / "training_features.json", orient="records", date_format="iso", double_precision=6)
    print(f"Wrote training_features: {len(training_features):,} rows -> {DATA_DIR / 'training_features.json'}")

    save_df(feature_store, "feature_store")
    print("\nFeature engineering complete.")
    print(f"FeatureStore columns: {list(feature_store.columns)}")
    print(feature_store.describe())


if __name__ == "__main__":
    main()