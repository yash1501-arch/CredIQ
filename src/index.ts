import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import { PrismaClient, RiskBand, LoanType } from "@prisma/client";

dotenv.config();

const app = express();
const prisma = new PrismaClient();
const PORT = process.env.PORT || 3000;
const ML_SERVICE_URL = process.env.ML_SERVICE_URL || "http://localhost:8000";

app.use(cors());
app.use(express.json());

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
async function callMLPredict(borrowerId: string, features: any) {
  const res = await fetch(`${ML_SERVICE_URL}/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(features),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`ML service error: ${err}`);
  }
  return res.json();
}

async function callMLMetrics() {
  const res = await fetch(`${ML_SERVICE_URL}/model-metrics`);
  if (!res.ok) throw new Error("ML metrics fetch failed");
  return res.json();
}

// ---------------------------------------------------------------------------
// POST /api/borrowers/:id/score — trigger scoring, persist result
// ---------------------------------------------------------------------------
app.post("/api/borrowers/:id/score", async (req, res) => {
  try {
    const borrowerId = req.params.id;
    const loanType = req.body.loanType as LoanType;

    if (!loanType) {
      return res.status(400).json({ error: "loanType is required" });
    }

    // Fetch borrower's latest feature snapshot from FeatureStore
    const featureSnap = await prisma.featureStore.findFirst({
      where: { borrowerId },
      orderBy: { asOfDate: "desc" },
    });

    if (!featureSnap) {
      return res.status(404).json({ error: "No feature snapshot found for borrower" });
    }

    // Fetch bureau record
    const bureau = await prisma.bureauRecord.findFirst({
      where: { borrowerId },
      orderBy: { asOfDate: "desc" },
    });

    // Build feature vector for ML service
    const features = {
      borrowerId,
      loanType,
      gstDelayAvgDays: Number(featureSnap.gstDelayAvgDays),
      gstOnTimeRatio: 0.8, // Would compute from GST filings; hardcoded for demo
      upiVolatilityIndex: Number(featureSnap.upiVolatilityIndex),
      epfoConsistencyRatio: Number(featureSnap.epfoConsistencyRatio),
      debtToIncomeProxy: Number(featureSnap.debtToIncomeProxy),
      utilizationTrend: Number(featureSnap.utilizationTrend),
      creditScore: bureau?.creditScore || 650,
      delinquencies12m: bureau?.delinquencies12m || 0,
    };

    // Call ML service
    const mlResult = await callMLPredict(borrowerId, features);

    // Get or create ModelRun record
    let modelRun = await prisma.modelRun.findFirst({
      where: {
        version: mlResult.modelVersion,
        loanType: loanType,
      },
    });

    if (!modelRun) {
      modelRun = await prisma.modelRun.create({
        data: {
          id: mlResult.modelRunId,
          version: mlResult.modelVersion,
          loanType: loanType,
          trainedAt: new Date(),
          accuracy: mlResult.shapDrivers ? 0.7 : 0, // placeholder
          aucRoc: 0.75,
          precision: 0.7,
          recall: 0.65,
          metricsJson: {},
        },
      });
    }

    // Persist RiskScore
    const riskScore = await prisma.riskScore.create({
      data: {
        borrowerId,
        loanId: req.body.loanId || null,
        modelRunId: modelRun.id,
        probDefault: mlResult.probDefault,
        score0to100: mlResult.score0to100,
        riskBand: mlResult.riskBand as RiskBand,
      },
    });

    // Persist RiskExplanations
    await prisma.riskExplanation.createMany({
      data: mlResult.shapDrivers.map((d: any, idx: number) => ({
        riskScoreId: riskScore.id,
        featureName: d.feature,
        shapValue: d.shapValue,
        direction: d.direction,
        rank: idx + 1,
      })),
    });

    res.json({
      riskScoreId: riskScore.id,
      ...mlResult,
    });
  } catch (err: any) {
    console.error("Score error:", err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// GET /api/borrowers/:id/risk — latest score + explanation
// ---------------------------------------------------------------------------
app.get("/api/borrowers/:id/risk", async (req, res) => {
  try {
    const borrowerId = req.params.id;

    const riskScore = await prisma.riskScore.findFirst({
      where: { borrowerId },
      orderBy: { computedAt: "desc" },
      include: {
        explanations: { orderBy: { rank: "asc" } },
        modelRun: true,
      },
    });

    if (!riskScore) {
      return res.status(404).json({ error: "No risk score found" });
    }

    const explanations = riskScore.explanations.map((e) => ({
      featureName: e.featureName,
      shapValue: Number(e.shapValue),
      direction: e.direction,
      plainEnglish:
        e.direction === "increases_risk"
          ? `${e.featureName} increased risk by ${Math.abs(Number(e.shapValue)) * 100:.1f} points`
          : `${e.featureName} decreased risk by ${Math.abs(Number(e.shapValue)) * 100:.1f} points`,
      rank: e.rank,
    }));

    res.json({
      borrowerId,
      riskScoreId: riskScore.id,
      probDefault: Number(riskScore.probDefault),
      score0to100: riskScore.score0to100,
      riskBand: riskScore.riskBand,
      computedAt: riskScore.computedAt,
      modelRun: {
        id: riskScore.modelRun.id,
        version: riskScore.modelRun.version,
        loanType: riskScore.modelRun.loanType,
        aucRoc: Number(riskScore.modelRun.aucRoc),
      },
      explanations,
    });
  } catch (err: any) {
    console.error("Get risk error:", err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// GET /api/portfolio/summary — aggregate stress heatmap data
// ---------------------------------------------------------------------------
app.get("/api/portfolio/summary", async (req, res) => {
  try {
    const scores = await prisma.riskScore.findMany({
      include: {
        borrower: { select: { sector: true, isMsme: true } },
        loan: { select: { loanType: true } },
        modelRun: { select: { loanType: true } },
      },
      orderBy: { computedAt: "desc" },
      take: 1000,
    });

    // Aggregate by sector x loanType
    const heatmap: Record<string, Record<string, { low: number; medium: number; high: number; critical: number; total: number }>> = {};

    for (const s of scores) {
      const sector = s.borrower?.sector || "Unknown";
      const loanType = s.loan?.loanType || s.modelRun?.loanType || "Unknown";
      if (!heatmap[sector]) heatmap[sector] = {};
      if (!heatmap[sector][loanType]) {
        heatmap[sector][loanType] = { low: 0, medium: 0, high: 0, critical: 0, total: 0 };
      }
      heatmap[sector][loanType][s.riskBand.toLowerCase()]++;
      heatmap[sector][loanType].total++;
    }

    // Overall stats
    const total = scores.length;
    const byBand = scores.reduce(
      (acc, s) => {
        acc[s.riskBand.toLowerCase()] = (acc[s.riskBand.toLowerCase()] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>
    );

    res.json({
      totalBorrowersScored: total,
      riskDistribution: byBand,
      heatmap,
      generatedAt: new Date().toISOString(),
    });
  } catch (err: any) {
    console.error("Portfolio summary error:", err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// GET /api/loans/:loanType/model-metrics — per-segment metrics
// ---------------------------------------------------------------------------
app.get("/api/loans/:loanType/model-metrics", async (req, res) => {
  try {
    const loanType = req.params.loanType.toUpperCase() as LoanType;

    // Try DB first
    const modelRuns = await prisma.modelRun.findMany({
      where: { loanType },
      orderBy: { trainedAt: "desc" },
      take: 5,
    });

    if (modelRuns.length > 0) {
      return res.json({
        loanType,
        source: "database",
        runs: modelRuns.map((m) => ({
          id: m.id,
          version: m.version,
          trainedAt: m.trainedAt,
          accuracy: Number(m.accuracy),
          aucRoc: Number(m.aucRoc),
          precision: Number(m.precision),
          recall: Number(m.recall),
          metricsJson: m.metricsJson,
        })),
      });
    }

    // Fallback to ML service
    const mlMetrics = await callMLMetrics();
    const segmentMetrics = mlMetrics.segments[loanType] || {};

    res.json({
      loanType,
      source: "ml-service",
      latest: {
        version: mlMetrics.modelVersion,
        modelRunId: mlMetrics.modelRunId,
        ...segmentMetrics,
      },
    });
  } catch (err: any) {
    console.error("Model metrics error:", err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// GET /api/borrowers/search?q= — search borrowers by name/sector
// ---------------------------------------------------------------------------
app.get("/api/borrowers/search", async (req, res) => {
  try {
    const q = (req.query.q as string) || "";
    const borrowers = await prisma.borrower.findMany({
      where: {
        OR: [
          { name: { contains: q, mode: "insensitive" } },
          { sector: { contains: q, mode: "insensitive" } },
        ],
      },
      take: 20,
      orderBy: { name: "asc" },
    });
    res.json(borrowers);
  } catch (err: any) {
    console.error("Search error:", err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------
app.get("/health", (req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
app.listen(PORT, () => {
  console.log(`API service running on http://localhost:${PORT}`);
  console.log(`ML service: ${ML_SERVICE_URL}`);
});