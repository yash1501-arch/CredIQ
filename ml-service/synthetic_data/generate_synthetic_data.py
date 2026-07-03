"""
Synthetic data generator for CredIQ MSME credit-risk MVP.

Produces correlated structured + alternate-data records that mirror the
Prisma schema.  A latent risk score drives:
  - lower bureau credit score
  - higher credit utilization and existing debt
  - higher GST filing delays
  - higher UPI inflow volatility
  - lower EPFO contribution consistency
  - higher 12-month probability of default

Outputs JSON files consumed by prisma/seed.ts.
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

np.random.seed(42)
fake = Faker("en_IN")
Faker.seed(42)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
N_BORROWERS = 3_000
SNAPSHOT_DATE = datetime(2025, 12, 31)
GST_PERIODS = pd.date_range(end=SNAPSHOT_DATE, periods=12, freq="ME").to_pydatetime().tolist()
EPFO_PERIODS = GST_PERIODS
UPI_DAYS = 90  # last 3 months
OUTPUT_DIR = Path(__file__).parent / "data"

LOAN_TYPES = ["PERSONAL", "HOME", "MORTGAGE", "AUTO", "MSME"]
LOAN_WEIGHTS = [0.30, 0.25, 0.20, 0.20, 0.05]
LOAN_TYPE_EFFECT = {
    "PERSONAL": 0.80,
    "AUTO": 0.20,
    "HOME": -0.30,
    "MORTGAGE": -0.40,
    "MSME": 0.50,
}
SECTORS = [
    "Manufacturing", "Trading", "Services", "Construction",
    "Textiles", "Food Processing", "IT Services", "Retail",
    "Healthcare", "Transport", "Agriculture", "Education",
]


def to_iso(dt: datetime) -> str:
    return dt.isoformat()


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


# ---------------------------------------------------------------------------
# Borrower + latent risk
# ---------------------------------------------------------------------------
def generate_borrowers(n: int) -> pd.DataFrame:
    """Create borrowers with a latent 0-1 risk score used to correlate signals."""
    ids = [str(uuid.uuid4()) for _ in range(n)]
    # Bimodal risk: most borrowers low risk, some high risk
    # Mix two betas: 70% Beta(1.5, 8) low risk, 30% Beta(5, 2) high risk
    low_risk = np.random.beta(1.5, 8, size=int(n * 0.7))
    high_risk = np.random.beta(5, 2, size=n - len(low_risk))
    base_risk = np.concatenate([low_risk, high_risk])
    np.random.shuffle(base_risk)
    
    stability = np.random.normal(0, 1, size=n)

    rows = []
    for i in range(n):
        reg_date = fake.date_between(start_date="-15y", end_date="-6m")
        rows.append({
            "id": ids[i],
            "name": fake.name(),
            "isMsme": np.random.random() < 0.75,
            "sector": np.random.choice(SECTORS),
            "registrationAt": datetime.combine(reg_date, datetime.min.time()).isoformat(),
            "ntbFlag": np.random.random() < 0.08,
            "ntcFlag": np.random.random() < 0.06,
            "baseRisk": base_risk[i],
            "stability": stability[i],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------
def generate_loans(borrowers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, b in borrowers.iterrows():
        loan_type = np.random.choice(LOAN_TYPES, p=LOAN_WEIGHTS)
        disbursed = fake.date_between(start_date="-5y", end_date="-3m")
        if loan_type == "PERSONAL":
            principal = int(np.clip(np.random.lognormal(11.5, 0.4), 25_000, 25_00_000))
            tenure = int(np.random.choice([12, 24, 36, 48], p=[0.1, 0.25, 0.35, 0.3]))
        elif loan_type == "AUTO":
            principal = int(np.clip(np.random.lognormal(12.2, 0.35), 2_00_000, 25_00_000))
            tenure = int(np.random.choice([36, 48, 60, 84], p=[0.1, 0.25, 0.45, 0.2]))
        elif loan_type == "HOME":
            principal = int(np.clip(np.random.lognormal(15.5, 0.45), 15_00_000, 3_00_00_000))
            tenure = int(np.random.choice([120, 180, 240, 300], p=[0.1, 0.25, 0.45, 0.2]))
        elif loan_type == "MORTGAGE":
            principal = int(np.clip(np.random.lognormal(15.8, 0.45), 25_00_000, 10_00_00_000))
            tenure = int(np.random.choice([60, 120, 180, 240], p=[0.1, 0.25, 0.45, 0.2]))
        else:  # MSME
            principal = int(np.clip(np.random.lognormal(14.5, 0.6), 5_00_000, 5_00_00_000))
            tenure = int(np.random.choice([12, 24, 36, 48, 60], p=[0.15, 0.25, 0.30, 0.20, 0.10]))

        rows.append({
            "id": str(uuid.uuid4()),
            "borrowerId": b["id"],
            "loanType": loan_type,
            "principal": principal,
            "tenureMonths": tenure,
            "disbursedAt": datetime.combine(disbursed, datetime.min.time()).isoformat(),
            "status": np.random.choice(
                ["active", "active", "active", "closed", "npa", "restructured"],
                p=[0.72, 0.15, 0.08, 0.02, 0.02, 0.01],
            ),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Bureau records
# ---------------------------------------------------------------------------
def generate_bureau_records(borrowers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, b in borrowers.iterrows():
        r = b["baseRisk"]
        # Near-deterministic from baseRisk
        credit_score_norm = np.clip(1.0 - r**0.3 + np.random.normal(0, 0.015), 0, 1)
        rows.append({
            "id": str(uuid.uuid4()),
            "borrowerId": b["id"],
            "creditScore": int(np.clip(300 + credit_score_norm * 600, 300, 900)),
            "existingDebt": round(float(np.clip(r * 8_000_000 + np.random.exponential(10_000), 0, 2_00_00_000)), 2),
            "utilizationPct": round(float(np.clip(r * 100 + np.random.normal(0, 2), 0, 100)), 2),
            "delinquencies12m": int(np.clip(np.random.poisson(r * 12), 0, 30)),
            "asOfDate": to_iso(SNAPSHOT_DATE),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# GST filings
# ---------------------------------------------------------------------------
def generate_gst_filings(borrowers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, b in borrowers.iterrows():
        r = b["baseRisk"]
        annual_turnover = np.random.lognormal(mean=14.5 + (1 - r) * 1.0, sigma=0.3)
        monthly_turnover = annual_turnover / 12
        for period_dt in GST_PERIODS:
            delay_mean = r * 50 + np.random.exponential(1)
            delay_days = int(np.clip(np.random.exponential(delay_mean + 0.5), 0, 90))
            filed_on_time = delay_days <= 5
            turnover = monthly_turnover * (1 + np.random.normal(0, 0.05) - r * 0.3)
            rows.append({
                "id": str(uuid.uuid4()),
                "borrowerId": b["id"],
                "period": period_dt.strftime("%Y-%m"),
                "turnover": round(float(max(turnover, 1_000)), 2),
                "filedOnTime": bool(filed_on_time),
                "delayDays": delay_days,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# UPI transactions
# ---------------------------------------------------------------------------
def generate_upi_transactions(borrowers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    counterparty_types = ["customer", "vendor", "personal", "utility", "loan_emi"]
    for _, b in borrowers.iterrows():
        r = b["baseRisk"]
        daily_inflow_mean = max(1_000, np.random.lognormal(9.0, 0.4) * (1 - r * 0.6))
        inflow_cv = 0.05 + r * 1.2 + max(0, np.random.normal(0, 0.02))
        outflow_mean = daily_inflow_mean * (0.65 + np.random.normal(0, 0.05))

        for day_offset in range(UPI_DAYS):
            txn_date = SNAPSHOT_DATE - timedelta(days=day_offset)
            weekend_factor = 0.3 if txn_date.weekday() >= 5 else 1.0
            n_in = max(0, int(np.random.poisson(5 * weekend_factor)))
            n_out = max(0, int(np.random.poisson(5 * weekend_factor)))

            for _ in range(n_in):
                amount = max(50, np.random.lognormal(
                    np.log(daily_inflow_mean / 2), inflow_cv
                ) * weekend_factor)
                rows.append({
                    "id": str(uuid.uuid4()),
                    "borrowerId": b["id"],
                    "txnDate": to_iso(txn_date),
                    "amount": round(float(amount), 2),
                    "direction": "inflow",
                    "counterpartyType": np.random.choice(counterparty_types, p=[0.6, 0.08, 0.08, 0.14, 0.1]),
                })
            for _ in range(n_out):
                amount = max(50, np.random.lognormal(
                    np.log(outflow_mean / 2), max(0.05, inflow_cv * 0.5)
                ) * weekend_factor)
                rows.append({
                    "id": str(uuid.uuid4()),
                    "borrowerId": b["id"],
                    "txnDate": to_iso(txn_date),
                    "amount": round(float(amount), 2),
                    "direction": "outflow",
                    "counterpartyType": np.random.choice(counterparty_types, p=[0.05, 0.7, 0.05, 0.1, 0.1]),
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# EPFO contributions
# ---------------------------------------------------------------------------
def generate_epfo_contributions(borrowers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, b in borrowers.iterrows():
        r = b["baseRisk"]
        consistency_ratio = np.clip(1.0 - r * 0.95 + np.random.normal(0, 0.02), 0.01, 0.99)
        employee_count = max(1, int(np.random.lognormal(2.5 - r * 0.6, 0.3)))
        base_contribution_per_employee = max(1_000, np.random.lognormal(8.5, 0.15))
        for period_dt in EPFO_PERIODS:
            is_consistent = np.random.random() < consistency_ratio
            contribution = employee_count * base_contribution_per_employee * (
                1.0 if is_consistent else np.random.choice([0.0, 0.15, 0.4], p=[0.3, 0.4, 0.3])
            )
            rows.append({
                "id": str(uuid.uuid4()),
                "borrowerId": b["id"],
                "period": period_dt.strftime("%Y-%m"),
                "employeeCount": employee_count,
                "contribution": round(float(contribution), 2),
                "isConsistent": bool(is_consistent),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Default labels
# ---------------------------------------------------------------------------
def generate_labels(borrowers: pd.DataFrame, loans: pd.DataFrame) -> pd.DataFrame:
    """
    12-month forward default flag per borrower/loan.
    Driven by latent risk + loan-type baseline so the model has learnable signal.
    """
    rows = []
    for _, b in borrowers.iterrows():
        borrower_loans = loans[loans["borrowerId"] == b["id"]]
        for _, loan in borrower_loans.iterrows():
            loan_type = loan["loanType"]
            logit = (
                -1.5
                + 6.0 * b["baseRisk"]
                + LOAN_TYPE_EFFECT[loan_type]
                + 0.2 * b["stability"]
                + np.random.normal(0, 0.15)
            )
            p_default = float(sigmoid(np.array([logit]))[0])
            rows.append({
                "borrowerId": b["id"],
                "loanId": loan["id"],
                "loanType": loan_type,
                "baseRisk": round(float(b["baseRisk"]), 4),
                "probDefault": round(p_default, 4),
                "default12m": int(np.random.random() < p_default),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def to_records(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to plain dicts (JSON serializable)."""
    return df.to_dict(orient="records")


def save_json(df: pd.DataFrame, name: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.json"
    path.write_text(json.dumps(to_records(df), indent=2, default=str))
    print(f"Wrote {name}: {len(df):,} rows -> {path}")


def main() -> None:
    print(f"Generating synthetic data for {N_BORROWERS:,} borrowers...")
    borrowers = generate_borrowers(N_BORROWERS)
    loans = generate_loans(borrowers)
    bureau = generate_bureau_records(borrowers)
    gst = generate_gst_filings(borrowers)
    upi = generate_upi_transactions(borrowers)
    epfo = generate_epfo_contributions(borrowers)
    labels = generate_labels(borrowers, loans)

    # Drop internal construction columns before saving.
    borrowers_out = borrowers.drop(columns=["baseRisk", "stability"])

    save_json(borrowers_out, "borrowers")
    save_json(loans, "loans")
    save_json(bureau, "bureau_records")
    save_json(gst, "gst_filings")
    save_json(upi, "upi_transactions")
    save_json(epfo, "epfo_contributions")
    save_json(labels, "labels")

    print("\nClass balance:")
    print(labels["default12m"].value_counts(normalize=True).round(3))
    print("Mean default rate:", labels["default12m"].mean().round(3))


if __name__ == "__main__":
    main()
