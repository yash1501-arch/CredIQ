export default {
  migrations: {
    path: "prisma/migrations",
    seed: "tsx prisma/seed.ts",
  },
  generator: {
    output: "generated/prisma",
  },
};