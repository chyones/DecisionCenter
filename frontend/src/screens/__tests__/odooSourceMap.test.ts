import { describe, expect, it } from 'vitest';

import {
  confidencePill,
  groupSourcesByDisplayGroup,
  hasWarnings,
  recordCountLabel,
  scanStatusPill,
} from '../odooSourceMap';
import { makeSourceMap } from './odooSourceMap.fixture';

describe('groupSourcesByDisplayGroup', () => {
  it('buckets every source into its display groups (13 groups)', () => {
    const groups = groupSourcesByDisplayGroup(makeSourceMap());
    expect(groups).toHaveLength(13);
    const names = groups.map((g) => g.group);
    expect(names).toContain('Project identity');
    expect(names).toContain('Payroll');
    expect(names).toContain('Attachments');
  });

  it('places multi-group sources in each of their groups', () => {
    const groups = groupSourcesByDisplayGroup(makeSourceMap());
    const payroll = groups.find((g) => g.group === 'Payroll')!;
    const manpower = groups.find((g) => g.group === 'Manpower / staff')!;
    expect(payroll.sources.some((s) => s.key === 'worked_days')).toBe(true);
    expect(manpower.sources.some((s) => s.key === 'worked_days')).toBe(true);
  });

  it('counts mappable vs total per group', () => {
    const data = makeSourceMap();
    data.sources = data.sources.map((s) =>
      s.key === 'purchase_orders' ? { ...s, mappable: false } : s,
    );
    const groups = groupSourcesByDisplayGroup(data);
    const po = groups.find((g) => g.group === 'RFQ / LPO / PO')!;
    expect(po.totalCount).toBe(1);
    expect(po.mappableCount).toBe(0);
  });
});

describe('recordCountLabel', () => {
  it('renders dash before scan, number after, and 100+ when capped', () => {
    const base = makeSourceMap().sources[0];
    expect(recordCountLabel({ ...base, record_count: null })).toBe('—');
    expect(recordCountLabel({ ...base, record_count: 3, capped: false })).toBe('3');
    expect(recordCountLabel({ ...base, record_count: 100, capped: true })).toBe('100+');
  });
});

describe('scanStatusPill', () => {
  it('maps statuses to pill values', () => {
    expect(scanStatusPill('ok').status).toBe('connected');
    expect(scanStatusPill('capped').status).toBe('connected');
    expect(scanStatusPill('empty').status).toBe('unknown');
    expect(scanStatusPill('unmapped').status).toBe('disconnected');
    expect(scanStatusPill('error: RuntimeError').status).toBe('failed');
    expect(scanStatusPill('not_scanned').status).toBe('unknown');
  });
});

describe('confidencePill', () => {
  it('maps confidence to pill values', () => {
    expect(confidencePill('high').status).toBe('passed');
    expect(confidencePill('medium').status).toBe('needs_review');
  });
});

describe('hasWarnings', () => {
  it('detects a source-level caveat', () => {
    expect(hasWarnings(makeSourceMap())).toBe(true);
    const clean = makeSourceMap();
    clean.sources = clean.sources.map((s) => ({ ...s, warning: '' }));
    expect(hasWarnings(clean)).toBe(false);
  });
});
