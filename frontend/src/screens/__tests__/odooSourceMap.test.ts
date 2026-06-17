import { describe, expect, it } from 'vitest';

import {
  confidencePill,
  durationLabel,
  failedSourceCount,
  groupSourcesByDisplayGroup,
  hasWarnings,
  isScanActive,
  recordCountLabel,
  scanProgressLabel,
  scanProgressPercent,
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
  it('maps the full batched-scan vocabulary to pill values', () => {
    expect(scanStatusPill('completed').status).toBe('connected');
    expect(scanStatusPill('running').status).toBe('processing');
    expect(scanStatusPill('pending').status).toBe('unknown');
    expect(scanStatusPill('partial').status).toBe('degraded');
    expect(scanStatusPill('capped').status).toBe('degraded');
    expect(scanStatusPill('empty').status).toBe('unknown');
    expect(scanStatusPill('timeout').status).toBe('failed');
    expect(scanStatusPill('failed').status).toBe('failed');
    expect(scanStatusPill('unmapped').status).toBe('disconnected');
    // back-compat with legacy single-shot statuses
    expect(scanStatusPill('ok').status).toBe('connected');
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

const PROGRESS = {
  total: 22,
  done: 12,
  pending: 8,
  running: 2,
  completed: 9,
  partial: 1,
  capped: 0,
  empty: 1,
  failed: 1,
  timeout: 0,
  unmapped: 0,
};

describe('scan progress helpers', () => {
  it('summarises progress with running/partial/failed counts', () => {
    const label = scanProgressLabel(PROGRESS);
    expect(label).toContain('12/22 scanned');
    expect(label).toContain('2 running');
    expect(label).toContain('1 partial');
    expect(label).toContain('1 failed');
    expect(scanProgressLabel(null)).toBe('');
  });

  it('computes a 0-100 percent', () => {
    expect(scanProgressPercent(PROGRESS)).toBe(55);
    expect(scanProgressPercent({ ...PROGRESS, total: 0, done: 0 })).toBe(0);
    expect(scanProgressPercent(null)).toBe(0);
  });
});

describe('isScanActive', () => {
  it('is true only while a session is pending/running', () => {
    expect(isScanActive(null)).toBe(false);
    expect(isScanActive(makeSourceMap())).toBe(false); // no session id
    expect(
      isScanActive(makeSourceMap({ scan_session_id: 's1', scan_state: 'running' })),
    ).toBe(true);
    expect(
      isScanActive(makeSourceMap({ scan_session_id: 's1', scan_state: 'pending' })),
    ).toBe(true);
    expect(
      isScanActive(makeSourceMap({ scan_session_id: 's1', scan_state: 'completed' })),
    ).toBe(false);
  });
});

describe('failedSourceCount', () => {
  it('counts only failed + timeout sources', () => {
    const data = makeSourceMap();
    data.sources = data.sources.map((s, i) => {
      if (i === 0) return { ...s, last_scan_status: 'failed' };
      if (i === 1) return { ...s, last_scan_status: 'timeout' };
      if (i === 2) return { ...s, last_scan_status: 'completed' };
      return s;
    });
    expect(failedSourceCount(data)).toBe(2);
    expect(failedSourceCount(null)).toBe(0);
  });
});

describe('durationLabel', () => {
  it('formats ms and seconds', () => {
    expect(durationLabel(null)).toBe('');
    expect(durationLabel(340)).toBe('340ms');
    expect(durationLabel(1200)).toBe('1.2s');
  });
});
