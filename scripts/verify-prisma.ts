import { prisma } from '../lib/prisma';

async function verify() {
  try {
    const counts = await Promise.all([
      prisma.borrower.count(),
      prisma.loan.count(),
      prisma.gstFiling.count(),
      prisma.upiTransaction.count(),
      prisma.epfoContribution.count(),
      prisma.bureauRecord.count(),
    ]);

    console.log('✅ Connected');
    console.log('Borrowers:', counts[0]);
    console.log('Loans:', counts[1]);
    console.log('GST Filings:', counts[2]);
    console.log('UPI Transactions:', counts[3]);
    console.log('EPFO Contributions:', counts[4]);
    console.log('Bureau Records:', counts[5]);

    // Test a query
    const sample = await prisma.borrower.findFirst({
      include: { loans: true, bureauRecords: true, featureSnaps: true }
    });
    console.log('\nSample borrower:', sample?.name, '| Loans:', sample?.loans.length, '| Features:', sample?.featureSnaps.length);

  } catch (e) {
    console.error('❌ Verification failed:', e);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

verify();