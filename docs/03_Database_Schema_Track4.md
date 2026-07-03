# Database Schema
## IDBI Innovate 2026 — Track 04: Predictive AI for MSME Credit Risk & Early Warning

**Author:** Narayan
**Engine:** PostgreSQL
**ORM:** Prisma

---

## 1. Entity Overview

- `Borrower` — core profile (individual/MSME)
- `Loan` — one borrower can have many loans, across 4 loan types
- `GstFiling` — periodic GST filing records (alternate data)
- `UpiTransaction` — UPI transaction stream (alternate data)
- `EpfoContribution` — periodic EPFO records (alternate data)
- `BureauRecord` — structured credit bureau snapshot
- `FeatureStore` — engineered features, point-in-time snapshot per borrower
- `ModelRun` — a trained model version + its metrics
- `RiskScore` — a prediction output, tied to a `ModelRun`
- `RiskExplanation` — SHAP driver breakdown for a `RiskScore`

Each alternate-data table is deliberately shaped to mirror what IDBI's sandbox is expected to expose (transactions, MSME financials, UPI patterns), so swapping the synthetic source for the real one later is a data-loading change, not a schema change.

## 2. Prisma Schema

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

enum LoanType {
  PERSONAL
  HOME
  MORTGAGE
  AUTO
  MSME
}

enum RiskBand {
  LOW
  MEDIUM
  HIGH
  CRITICAL
}

model Borrower {
  id              String   @id @default(uuid())
  name            String
  isMsme          Boolean  @default(false)
  sector          String?
  registrationAt  DateTime?
  ntbFlag         Boolean  @default(false) // New-to-Bank
  ntcFlag         Boolean  @default(false) // New-to-Credit
  createdAt       DateTime @default(now())

  loans           Loan[]
  gstFilings      GstFiling[]
  upiTransactions UpiTransaction[]
  epfoRecords     EpfoContribution[]
  bureauRecords   BureauRecord[]
  featureSnaps    FeatureStore[]
  riskScores      RiskScore[]
}

model Loan {
  id              String   @id @default(uuid())
  borrowerId      String
  borrower        Borrower @relation(fields: [borrowerId], references: [id])
  loanType        LoanType
  principal       Decimal
  tenureMonths    Int
  disbursedAt     DateTime
  status          String   // active, closed, npa, restructured
  createdAt       DateTime @default(now())

  riskScores      RiskScore[]
}

model GstFiling {
  id              String   @id @default(uuid())
  borrowerId      String
  borrower        Borrower @relation(fields: [borrowerId], references: [id])
  period          String   // e.g. "2026-05"
  turnover        Decimal
  filedOnTime     Boolean
  delayDays       Int      @default(0)
  createdAt       DateTime @default(now())
}

model UpiTransaction {
  id              String   @id @default(uuid())
  borrowerId      String
  borrower        Borrower @relation(fields: [borrowerId], references: [id])
  txnDate         DateTime
  amount          Decimal
  direction       String   // inflow / outflow
  counterpartyType String  // vendor, customer, personal, etc.
  createdAt       DateTime @default(now())
}

model EpfoContribution {
  id              String   @id @default(uuid())
  borrowerId      String
  borrower        Borrower @relation(fields: [borrowerId], references: [id])
  period          String
  employeeCount   Int
  contribution    Decimal
  isConsistent    Boolean  @default(true)
  createdAt       DateTime @default(now())
}

model BureauRecord {
  id              String   @id @default(uuid())
  borrowerId      String
  borrower        Borrower @relation(fields: [borrowerId], references: [id])
  creditScore     Int
  existingDebt    Decimal
  utilizationPct  Decimal
  delinquencies12m Int
  asOfDate        DateTime
  createdAt       DateTime @default(now())
}

model FeatureStore {
  id                    String   @id @default(uuid())
  borrowerId            String
  borrower              Borrower @relation(fields: [borrowerId], references: [id])
  asOfDate              DateTime
  gstDelayAvgDays       Decimal
  upiVolatilityIndex    Decimal
  epfoConsistencyRatio  Decimal
  debtToIncomeProxy     Decimal
  utilizationTrend      Decimal
  createdAt             DateTime @default(now())

  @@index([borrowerId, asOfDate])
}

model ModelRun {
  id            String   @id @default(uuid())
  version       String
  loanType      LoanType
  trainedAt     DateTime @default(now())
  accuracy      Decimal
  aucRoc        Decimal
  precision     Decimal
  recall        Decimal
  metricsJson   Json

  riskScores    RiskScore[]
}

model RiskScore {
  id              String   @id @default(uuid())
  borrowerId      String
  borrower        Borrower @relation(fields: [borrowerId], references: [id])
  loanId          String?
  loan            Loan?    @relation(fields: [loanId], references: [id])
  modelRunId      String
  modelRun        ModelRun @relation(fields: [modelRunId], references: [id])
  probDefault     Decimal
  score0to100     Int
  riskBand        RiskBand
  computedAt      DateTime @default(now())

  explanations    RiskExplanation[]

  @@index([borrowerId, computedAt])
}

model RiskExplanation {
  id            String    @id @default(uuid())
  riskScoreId   String
  riskScore     RiskScore @relation(fields: [riskScoreId], references: [id])
  featureName   String
  shapValue     Decimal
  direction     String    // increases_risk / decreases_risk
  rank          Int
}
```

## 3. Key Relationships
- `Borrower` 1—N `Loan`, `GstFiling`, `UpiTransaction`, `EpfoContribution`, `BureauRecord`, `FeatureStore`, `RiskScore`
- `ModelRun` 1—N `RiskScore` (every prediction traceable to the exact model version that produced it — important for the "consistent, comparable, actionable" framework requirement in the track brief)
- `RiskScore` 1—N `RiskExplanation` (top-N SHAP drivers per prediction)

## 4. Synthetic → Real Sandbox Field Mapping (for your pitch deck)
| Synthetic field | Expected real sandbox source |
|---|---|
| `GstFiling.*` | GSTN sandbox filing data |
| `UpiTransaction.*` | UPI transaction pattern sandbox |
| `EpfoContribution.*` | EPFO sandbox records |
| `BureauRecord.*` | Bureau/credit history sandbox |

Documenting this table in your submission is a strong signal to judges that the schema is production-intent, not a hackathon toy.
