#!/usr/bin/env node
/**
 * Bundle-size budget check — Phase 2C Slice 2.
 *
 * Validates production build artifacts against gzip budgets.
 * Run after `npm run build`.
 */

import { readdirSync, readFileSync } from 'fs';
import { gzipSync } from 'zlib';
import { join } from 'path';

const DIST = join(import.meta.dirname, '..', 'dist', 'assets');

const BUDGETS = {
  '.js': { perFile: 120 * 1024, total: 120 * 1024, label: 'JavaScript' },
  '.css': { perFile: 15 * 1024, total: 15 * 1024, label: 'CSS' },
};

function formatBytes(b) {
  return `${(b / 1024).toFixed(2)} kB`;
}

const files = readdirSync(DIST);
let exitCode = 0;

for (const [ext, budget] of Object.entries(BUDGETS)) {
  const matches = files.filter((f) => f.endsWith(ext));
  let totalRaw = 0;
  let totalGzip = 0;

  for (const name of matches) {
    const raw = readFileSync(join(DIST, name));
    const gz = gzipSync(raw);
    totalRaw += raw.length;
    totalGzip += gz.length;

    if (gz.length > budget.perFile) {
      console.error(
        `❌ ${budget.label} file exceeds per-file budget: ${name} (${formatBytes(gz.length)} gzip > ${formatBytes(budget.perFile)})`,
      );
      exitCode = 1;
    } else {
      console.log(`✅ ${name}: ${formatBytes(raw.length)} raw / ${formatBytes(gz.length)} gzip`);
    }
  }

  if (totalGzip > budget.total) {
    console.error(
      `❌ Total ${budget.label} exceeds budget: ${formatBytes(totalGzip)} gzip > ${formatBytes(budget.total)}`,
    );
    exitCode = 1;
  } else {
    console.log(`✅ Total ${budget.label}: ${formatBytes(totalGzip)} gzip / ${formatBytes(budget.total)} budget`);
  }
}

if (exitCode === 0) {
  console.log('✅ All bundle-size budgets passed.');
} else {
  console.error('❌ Bundle-size budget check failed.');
}
process.exit(exitCode);
