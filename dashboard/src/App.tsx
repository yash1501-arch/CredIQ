import { useState, useEffect } from 'react';
import './App.css';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:3000/api';
const ML_BASE = import.meta.env.VITE_ML_BASE || 'http://localhost:8000';

interface Borrower {
  id: string;
  name: string;
  isMsme: boolean;
  sector: string | null;
}

interface RiskScore {
  borrowerId: string;
  loanId: string | null;
  probDefault: number;
  score0to100: number;
  riskBand: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  modelRunId: string;
  computedAt: string;
}

interface SHAPDriver {
  feature: string;
  shapValue: number;
  direction: 'increases_risk' | 'decreases_risk';
  plainEnglish: string;
}

interface PredictionResponse {
  borrowerId: string;
  loanType: string;
  probDefault: number;
  score0to100: number;
  riskBand: string;
  modelRunId: string;
  modelVersion: string;
  shapDrivers: SHAPDriver[];
  computedAt: string;
}

interface PortfolioSummary {
  totalBorrowers: number;
  byRiskBand: Record<string, number>;
  byLoanType: Record<string, { total: number; avgScore: number }>;
  bySector: Record<string, { total: number; avgScore: number }>;
}

const RISK_BAND_COLORS: Record<string, string> = {
  LOW: 'bg-green-100 text-green-800 border-green-200',
  MEDIUM: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  HIGH: 'bg-orange-100 text-orange-800 border-orange-200',
  CRITICAL: 'bg-red-100 text-red-800 border-red-200',
};

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function SearchPanel({ onSearch, isLoading }: { onSearch: (id: string) => void; isLoading: boolean }) {
  const [query, setQuery] = useState('');
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Borrower Search</h2>
      <div className="flex gap-3 max-w-md">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && query.trim() && onSearch(query.trim())}
          placeholder="Enter Borrower ID"
          className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          disabled={isLoading}
        />
        <button
          onClick={() => query.trim() && onSearch(query.trim())}
          disabled={isLoading || !query.trim()}
          className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? 'Searching...' : 'Search'}
        </button>
      </div>
    </div>
  );
}

function RiskScoreCard({ data, drivers }: { data: PredictionResponse; drivers: SHAPDriver[] }) {
  const bandColor = RISK_BAND_COLORS[data.riskBand] || 'bg-gray-100 text-gray-800';
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <div className="text-center p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-500">Risk Score</p>
          <p className="text-4xl font-bold text-gray-900">{data.score0to100}/100</p>
        </div>
        <div className="text-center p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-500">Probability of Default</p>
          <p className="text-4xl font-bold text-gray-900">{(data.probDefault * 100).toFixed(1)}%</p>
        </div>
        <div className="text-center p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-500">Risk Band</p>
          <span className={`inline-block px-4 py-2 rounded-full text-sm font-semibold ${bandColor}`}>
            {data.riskBand}
          </span>
        </div>
      </div>

      <div className="border-t border-gray-200 pt-4">
        <h3 className="font-semibold text-gray-900 mb-3">Top Risk Drivers</h3>
        <div className="space-y-2">
          {drivers.map((driver, idx) => (
            <div key={idx} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
              <span className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                driver.direction === 'increases_risk' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
              }`}>
                {idx + 1}
              </span>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">{driver.plainEnglish}</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  SHAP value: {driver.shapValue > 0 ? '+' : ''}{driver.shapValue.toFixed(4)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200 text-sm text-gray-500">
        <p>Model: {data.modelVersion} | Run: {data.modelRunId.slice(0, 8)}...</p>
        <p>Computed: {formatDate(data.computedAt)}</p>
      </div>
    </div>
  );
}

function PortfolioHeatmap({ data }: { data: PortfolioSummary }) {
  const riskBands = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
  const maxCount = Math.max(...Object.values(data.byRiskBand));

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Portfolio Risk Heatmap</h2>
      
      <div className="mb-6">
        <h3 className="font-medium text-gray-900 mb-3">Risk Band Distribution</h3>
        <div className="grid grid-cols-4 gap-3">
          {riskBands.map((band) => {
            const count = data.byRiskBand[band] || 0;
            const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
            return (
              <div key={band} className={`p-4 rounded-lg ${RISK_BAND_COLORS[band]}`}>
                <div className="flex justify-between items-center mb-1">
                  <span className="font-semibold">{band}</span>
                  <span className="text-2xl font-bold">{count}</span>
                </div>
                <div className="h-2 bg-white/30 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-white/50 rounded-full transition-all duration-300"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h3 className="font-medium text-gray-900 mb-3">By Loan Type</h3>
          <div className="space-y-2">
            {Object.entries(data.byLoanType).map(([type, stats]) => (
              <div key={type} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                <span className="font-medium">{type}</span>
                <div className="text-right">
                  <p className="text-sm text-gray-600">{stats.total} loans</p>
                  <p className="text-sm font-semibold text-blue-600">Avg Score: {stats.avgScore.toFixed(0)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 className="font-medium text-gray-900 mb-3">By Sector</h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {Object.entries(data.bySector).slice(0, 8).map(([sector, stats]) => (
              <div key={sector} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                <span className="font-medium truncate pr-4">{sector}</span>
                <div className="text-right">
                  <p className="text-sm text-gray-600">{stats.total} borrowers</p>
                  <p className="text-sm font-semibold text-blue-600">Avg Score: {stats.avgScore.toFixed(0)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [borrowerId, setBorrowerId] = useState<string | null>(null);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load portfolio summary on mount
  useEffect(() => {
    fetch(`${API_BASE}/portfolio/summary`)
      .then((r) => r.json())
      .then(setPortfolio)
      .catch(() => {});
  }, []);

  const handleSearch = async (id: string) => {
    setIsLoading(true);
    setError(null);
    try {
      // Try to get from Express API first (which persists), fallback to ML service
      const response = await fetch(`${API_BASE}/borrowers/${id}/risk`);
      if (response.ok) {
        const data = await response.json();
        setPrediction(data);
      } else {
        // Fallback: call ML service directly with mock features
        // In real app, features would come from DB
        const mlResponse = await fetch(`${ML_BASE}/explain`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            borrowerId: id,
            loanType: 'PERSONAL',
            gstDelayAvgDays: 10,
            gstOnTimeRatio: 0.8,
            upiVolatilityIndex: 1.1,
            epfoConsistencyRatio: 0.9,
            debtToIncomeProxy: 0.5,
            utilizationTrend: 0.3,
            creditScore: 750,
            delinquencies12m: 0,
          }),
        });
        if (mlResponse.ok) {
          const data = await mlResponse.json();
          setPrediction(data);
        } else {
          throw new Error('Failed to fetch prediction');
        }
      }
      setBorrowerId(id);
    } catch (err) {
      setError('Failed to fetch risk score. Ensure API and ML services are running.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <h1 className="text-2xl font-bold text-gray-900">CredIQ</h1>
            </div>
            <span className="px-3 py-1 text-xs font-medium bg-blue-50 text-blue-700 rounded-full">
              IDBI Innovate 2026 — Track 04
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700" role="alert">
            {error}
          </div>
        )}

        <SearchPanel onSearch={handleSearch} isLoading={isLoading} />

        {prediction && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            <div className="lg:col-span-2">
              <RiskScoreCard data={prediction} drivers={prediction.shapDrivers} />
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h3 className="font-semibold text-gray-900 mb-4">Borrower Details</h3>
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-500">Borrower ID</dt>
                  <dd className="font-mono text-gray-900">{prediction.borrowerId}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Loan Type</dt>
                  <dd className="font-medium text-gray-900">{prediction.loanType}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Model Version</dt>
                  <dd className="font-mono text-gray-900">{prediction.modelVersion}</dd>
                </div>
              </dl>
            </div>
          </div>
        )}

        {portfolio && <PortfolioHeatmap data={portfolio} />}
      </main>

      <footer className="bg-white border-t border-gray-200 mt-12 py-6">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm text-gray-500">
          CredIQ — Predictive AI for MSME Credit Risk & Early Warning
          <br />
          Built for IDBI Innovate 2026 | Synthetic data only
        </div>
      </footer>
    </div>
  );
}

export default App;