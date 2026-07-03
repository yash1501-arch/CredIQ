-- CreateEnum
CREATE TYPE "LoanType" AS ENUM ('PERSONAL', 'HOME', 'MORTGAGE', 'AUTO', 'MSME');

-- CreateEnum
CREATE TYPE "RiskBand" AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');

-- CreateTable
CREATE TABLE "Borrower" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "isMsme" BOOLEAN NOT NULL DEFAULT false,
    "sector" TEXT,
    "registrationAt" TIMESTAMP(3),
    "ntbFlag" BOOLEAN NOT NULL DEFAULT false,
    "ntcFlag" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Borrower_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Loan" (
    "id" TEXT NOT NULL,
    "borrowerId" TEXT NOT NULL,
    "loanType" "LoanType" NOT NULL,
    "principal" DECIMAL(65,30) NOT NULL,
    "tenureMonths" INTEGER NOT NULL,
    "disbursedAt" TIMESTAMP(3) NOT NULL,
    "status" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Loan_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "GstFiling" (
    "id" TEXT NOT NULL,
    "borrowerId" TEXT NOT NULL,
    "period" TEXT NOT NULL,
    "turnover" DECIMAL(65,30) NOT NULL,
    "filedOnTime" BOOLEAN NOT NULL,
    "delayDays" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "GstFiling_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "UpiTransaction" (
    "id" TEXT NOT NULL,
    "borrowerId" TEXT NOT NULL,
    "txnDate" TIMESTAMP(3) NOT NULL,
    "amount" DECIMAL(65,30) NOT NULL,
    "direction" TEXT NOT NULL,
    "counterpartyType" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "UpiTransaction_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "EpfoContribution" (
    "id" TEXT NOT NULL,
    "borrowerId" TEXT NOT NULL,
    "period" TEXT NOT NULL,
    "employeeCount" INTEGER NOT NULL,
    "contribution" DECIMAL(65,30) NOT NULL,
    "isConsistent" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "EpfoContribution_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "BureauRecord" (
    "id" TEXT NOT NULL,
    "borrowerId" TEXT NOT NULL,
    "creditScore" INTEGER NOT NULL,
    "existingDebt" DECIMAL(65,30) NOT NULL,
    "utilizationPct" DECIMAL(65,30) NOT NULL,
    "delinquencies12m" INTEGER NOT NULL,
    "asOfDate" TIMESTAMP(3) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "BureauRecord_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "FeatureStore" (
    "id" TEXT NOT NULL,
    "borrowerId" TEXT NOT NULL,
    "asOfDate" TIMESTAMP(3) NOT NULL,
    "gstDelayAvgDays" DECIMAL(65,30) NOT NULL,
    "upiVolatilityIndex" DECIMAL(65,30) NOT NULL,
    "epfoConsistencyRatio" DECIMAL(65,30) NOT NULL,
    "debtToIncomeProxy" DECIMAL(65,30) NOT NULL,
    "utilizationTrend" DECIMAL(65,30) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "FeatureStore_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ModelRun" (
    "id" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "loanType" "LoanType" NOT NULL,
    "trainedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "accuracy" DECIMAL(65,30) NOT NULL,
    "aucRoc" DECIMAL(65,30) NOT NULL,
    "precision" DECIMAL(65,30) NOT NULL,
    "recall" DECIMAL(65,30) NOT NULL,
    "metricsJson" JSONB NOT NULL,

    CONSTRAINT "ModelRun_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RiskScore" (
    "id" TEXT NOT NULL,
    "borrowerId" TEXT NOT NULL,
    "loanId" TEXT,
    "modelRunId" TEXT NOT NULL,
    "probDefault" DECIMAL(65,30) NOT NULL,
    "score0to100" INTEGER NOT NULL,
    "riskBand" "RiskBand" NOT NULL,
    "computedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "RiskScore_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RiskExplanation" (
    "id" TEXT NOT NULL,
    "riskScoreId" TEXT NOT NULL,
    "featureName" TEXT NOT NULL,
    "shapValue" DECIMAL(65,30) NOT NULL,
    "direction" TEXT NOT NULL,
    "rank" INTEGER NOT NULL,

    CONSTRAINT "RiskExplanation_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "FeatureStore_borrowerId_asOfDate_idx" ON "FeatureStore"("borrowerId", "asOfDate");

-- CreateIndex
CREATE INDEX "RiskScore_borrowerId_computedAt_idx" ON "RiskScore"("borrowerId", "computedAt");

-- AddForeignKey
ALTER TABLE "Loan" ADD CONSTRAINT "Loan_borrowerId_fkey" FOREIGN KEY ("borrowerId") REFERENCES "Borrower"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "GstFiling" ADD CONSTRAINT "GstFiling_borrowerId_fkey" FOREIGN KEY ("borrowerId") REFERENCES "Borrower"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "UpiTransaction" ADD CONSTRAINT "UpiTransaction_borrowerId_fkey" FOREIGN KEY ("borrowerId") REFERENCES "Borrower"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "EpfoContribution" ADD CONSTRAINT "EpfoContribution_borrowerId_fkey" FOREIGN KEY ("borrowerId") REFERENCES "Borrower"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "BureauRecord" ADD CONSTRAINT "BureauRecord_borrowerId_fkey" FOREIGN KEY ("borrowerId") REFERENCES "Borrower"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "FeatureStore" ADD CONSTRAINT "FeatureStore_borrowerId_fkey" FOREIGN KEY ("borrowerId") REFERENCES "Borrower"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RiskScore" ADD CONSTRAINT "RiskScore_borrowerId_fkey" FOREIGN KEY ("borrowerId") REFERENCES "Borrower"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RiskScore" ADD CONSTRAINT "RiskScore_loanId_fkey" FOREIGN KEY ("loanId") REFERENCES "Loan"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RiskScore" ADD CONSTRAINT "RiskScore_modelRunId_fkey" FOREIGN KEY ("modelRunId") REFERENCES "ModelRun"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RiskExplanation" ADD CONSTRAINT "RiskExplanation_riskScoreId_fkey" FOREIGN KEY ("riskScoreId") REFERENCES "RiskScore"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
