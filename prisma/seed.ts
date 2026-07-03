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
  await prisma.riskExplanation.deleteMany({});
  await prisma.riskScore.deleteMany({});
  await prisma.modelRun.deleteMany({});
  await prisma.featureStore.deleteMany({});
  await prisma.bureauRecord.deleteMany({});
  await prisma.epfoContribution.deleteMany({});
  await prisma.upiTransaction.deleteMany({});
  await prisma.gstFiling.deleteMany({});
  await prisma.loan.deleteMany({});
  await prisma.borrower.deleteMany({});

  // Insert in dependency order.
  await prisma.borrower.createMany({ data: borrowers, skipDuplicates: true });
  await prisma.loan.createMany({ data: loans, skipDuplicates: true });
  await prisma.gstFiling.createMany({ data: gstFilings, skipDuplicates: true });
  await prisma.upiTransaction.createMany({ data: upiTransactions, skipDuplicates: true });
  await prisma.epfoContribution.createMany({ data: epfoContributions, skipDuplicates: true });
  await prisma.bureauRecord.createMany({ data: bureauRecords, skipDuplicates: true });

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
