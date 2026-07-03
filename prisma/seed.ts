import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient({
  log: process.env.NODE_ENV === 'production' ? ['error'] : ['info', 'warn', 'error'],
});

const DATA_DIR = path.join(__dirname, '..', 'ml-service', 'synthetic_data', 'data');

function loadJson<T>(name: string): T[] {
  const filePath = path.join(DATA_DIR, `${name}.json`);
  if (!fs.existsSync(filePath)) {
    throw new Error(`Seed data file not found: ${filePath}. Run the Python synthetic generator first.`);
  }
  return JSON.parse(fs.readFileSync(filePath, 'utf-8')) as T[];
}

function escape(val: any): string {
  if (val === null || val === undefined) return 'NULL';
  if (typeof val === 'string') return `'${val.replace(/'/g, "''")}'`;
  if (typeof val === 'boolean') return val ? 'TRUE' : 'FALSE';
  if (typeof val === 'number') return val.toString();
  if (val instanceof Date) return `'${val.toISOString()}'`;
  return `'${String(val).replace(/'/g, "''")}'`;
}

async function insertBatch(table: string, columns: string[], rows: any[][]) {
  if (rows.length === 0) return;
  const placeholders = rows.map(r => `(${r.map(escape).join(',')})`).join(',');
  const sql = `INSERT INTO "${table}" (${columns.map(c => `"${c}"`).join(',')}) VALUES ${placeholders} ON CONFLICT DO NOTHING`;
  await prisma.$executeRawUnsafe(sql);
}

async function main() {
  console.log('Loading synthetic data from', DATA_DIR);

  const borrowers = loadJson<any>('borrowers');
  const loans = loadJson<any>('loans');
  const gstFilings = loadJson<any>('gst_filings');
  const upiTransactions = loadJson<any>('upi_transactions');
  const epfoContributions = loadJson<any>('epfo_contributions');
  const bureauRecords = loadJson<any>('bureau_records');

  console.log(`Seeding ${borrowers.length} borrowers, ${loans.length} loans...`);

  // Wipe existing synthetic data in reverse dependency order.
  await prisma.$executeRawUnsafe('TRUNCATE "RiskExplanation", "RiskScore", "ModelRun", "FeatureStore", "BureauRecord", "EpfoContribution", "UpiTransaction", "GstFiling", "Loan", "Borrower" RESTART IDENTITY CASCADE');

  // Borrowers
  console.log('Seeding borrowers...');
  const borrowerCols = ['id', 'name', 'isMsme', 'sector', 'registrationAt', 'ntbFlag', 'ntcFlag', 'createdAt'];
  for (let i = 0; i < borrowers.length; i += 100) {
    const batch = borrowers.slice(i, i + 100).map(b => [
      b.id, b.name, b.isMsme, b.sector || null, b.registrationAt, b.ntbFlag, b.ntcFlag, b.createdAt || new Date().toISOString()
    ]);
    await insertBatch('Borrower', borrowerCols, batch);
  }

  // Loans
  console.log('Seeding loans...');
  const loanCols = ['id', 'borrowerId', 'loanType', 'principal', 'tenureMonths', 'disbursedAt', 'status', 'createdAt'];
  for (let i = 0; i < loans.length; i += 100) {
    const batch = loans.slice(i, i + 100).map(l => [
      l.id, l.borrowerId, l.loanType, l.principal, l.tenureMonths, l.disbursedAt, l.status, l.createdAt || new Date().toISOString()
    ]);
    await insertBatch('Loan', loanCols, batch);
  }

  // GST Filings
  console.log('Seeding GST filings...');
  const gstCols = ['id', 'borrowerId', 'period', 'turnover', 'filedOnTime', 'delayDays', 'createdAt'];
  for (let i = 0; i < gstFilings.length; i += 500) {
    const batch = gstFilings.slice(i, i + 500).map(g => [
      g.id, g.borrowerId, g.period, g.turnover, g.filedOnTime, g.delayDays, g.createdAt || new Date().toISOString()
    ]);
    await insertBatch('GstFiling', gstCols, batch);
  }

  // UPI Transactions
  console.log('Seeding UPI transactions...');
  const upiCols = ['id', 'borrowerId', 'txnDate', 'amount', 'direction', 'counterpartyType', 'createdAt'];
  for (let i = 0; i < upiTransactions.length; i += 500) {
    const batch = upiTransactions.slice(i, i + 500).map(u => [
      u.id, u.borrowerId, u.txnDate, u.amount, u.direction, u.counterpartyType, u.createdAt || new Date().toISOString()
    ]);
    await insertBatch('UpiTransaction', upiCols, batch);
  }

  // EPFO Contributions
  console.log('Seeding EPFO contributions...');
  const epfoCols = ['id', 'borrowerId', 'period', 'employeeCount', 'contribution', 'isConsistent', 'createdAt'];
  for (let i = 0; i < epfoContributions.length; i += 500) {
    const batch = epfoContributions.slice(i, i + 500).map(e => [
      e.id, e.borrowerId, e.period, e.employeeCount, e.contribution, e.isConsistent, e.createdAt || new Date().toISOString()
    ]);
    await insertBatch('EpfoContribution', epfoCols, batch);
  }

  // Bureau Records
  console.log('Seeding bureau records...');
  const bureauCols = ['id', 'borrowerId', 'creditScore', 'existingDebt', 'utilizationPct', 'delinquencies12m', 'asOfDate', 'createdAt'];
  for (let i = 0; i < bureauRecords.length; i += 100) {
    const batch = bureauRecords.slice(i, i + 100).map(b => [
      b.id, b.borrowerId, b.creditScore, b.existingDebt, b.utilizationPct, b.delinquencies12m, b.asOfDate, b.createdAt || new Date().toISOString()
    ]);
    await insertBatch('BureauRecord', bureauCols, batch);
  }

  console.log('Seed complete.');
}

main()
  .catch((e) => {
    console.error('Seed failed:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });