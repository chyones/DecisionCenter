import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { OdooSourceMapPanel } from '../OdooSourceMapPanel';
import { makeSourceMap } from './odooSourceMap.fixture';

describe('OdooSourceMapPanel', () => {
  it('shows loading then renders the generic map', () => {
    const { rerender } = render(
      <OdooSourceMapPanel data={null} loading scanning={false} onScan={() => {}} />,
    );
    expect(screen.getByText(/Loading Odoo source map/i)).toBeInTheDocument();

    rerender(
      <OdooSourceMapPanel data={makeSourceMap()} loading={false} scanning={false} onScan={() => {}} />,
    );
    expect(screen.getByTestId('odoo-source-map')).toBeInTheDocument();
    expect(screen.getByText('Generic Source Map')).toBeInTheDocument();
  });

  it('renders runtime ids (not hardcoded validation samples)', () => {
    render(
      <OdooSourceMapPanel data={makeSourceMap()} loading={false} scanning={false} onScan={() => {}} />,
    );
    expect(screen.getByText('99001')).toBeInTheDocument(); // odoo project id
    expect(screen.getByText('88002')).toBeInTheDocument(); // analytic id
    // No PRJ-001/002 validation-sample ids leak into the rendered map.
    expect(screen.queryByText('14602')).not.toBeInTheDocument();
    expect(screen.queryByText('21963')).not.toBeInTheDocument();
  });

  it('renders all 13 display groups', () => {
    render(
      <OdooSourceMapPanel data={makeSourceMap()} loading={false} scanning={false} onScan={() => {}} />,
    );
    for (const g of [
      'Project identity', 'Contract value', 'Actual cost', 'Accounting / journal lines',
      'Vendor bills', 'RFQ / LPO / PO', 'Purchase lines', 'Material requests',
      'Stock / deliveries', 'HR expenses', 'Payroll', 'Manpower / staff', 'Attachments',
    ]) {
      expect(screen.getByTestId(`source-group-${g}`)).toBeInTheDocument();
    }
  });

  it('renders the 9 denylisted/ambiguous paths', () => {
    render(
      <OdooSourceMapPanel data={makeSourceMap()} loading={false} scanning={false} onScan={() => {}} />,
    );
    const deny = screen.getByTestId('denylisted-paths');
    expect(deny).toHaveTextContent('purchase.order.project_id_mr');
    expect(deny).toHaveTextContent('account.move.project');
    expect(deny.querySelectorAll('span.line-through').length).toBe(9);
  });

  it('shows record counts after a scan, with 100+ for capped sources', () => {
    const scanned = makeSourceMap({ last_scanned_at: '2026-06-16T10:00:00Z' });
    scanned.sources = scanned.sources.map((s) => {
      if (s.key === 'purchase_orders') return { ...s, record_count: 100, capped: true, last_scan_status: 'capped' };
      if (s.key === 'material_requests') return { ...s, record_count: 3, last_scan_status: 'ok' };
      return s;
    });
    render(
      <OdooSourceMapPanel data={scanned} loading={false} scanning={false} onScan={() => {}} />,
    );
    expect(screen.getByTestId('source-row-purchase_orders')).toHaveTextContent('100+ records');
    expect(screen.getByTestId('source-row-material_requests')).toHaveTextContent('3 records');
  });

  it('surfaces warnings and gaps', () => {
    render(
      <OdooSourceMapPanel data={makeSourceMap()} loading={false} scanning={false} onScan={() => {}} />,
    );
    expect(screen.getByTestId('source-row-po_rfq_attachments')).toHaveTextContent('Re-verify after deploy.');
    // actual_cost is single-group; project_identity renders in two groups.
    expect(screen.getByTestId('source-row-actual_cost')).toHaveTextContent('CONNECTOR FIELD GAP');
  });

  it('lists missing/disabled sources when present', () => {
    const data = makeSourceMap({ missing_sources: ['purchase_orders', 'vendor_bills'] });
    render(<OdooSourceMapPanel data={data} loading={false} scanning={false} onScan={() => {}} />);
    expect(screen.getByText(/Missing \/ disabled sources \(2\)/)).toBeInTheDocument();
  });

  it('fires onScan when the scan button is clicked', () => {
    const onScan = vi.fn();
    render(<OdooSourceMapPanel data={makeSourceMap()} loading={false} scanning={false} onScan={onScan} />);
    fireEvent.click(screen.getByRole('button', { name: /Scan Odoo Sources/i }));
    expect(onScan).toHaveBeenCalledOnce();
  });

  it('disables scan when Odoo is not enabled', () => {
    const data = makeSourceMap({ odoo_enabled: false });
    render(<OdooSourceMapPanel data={data} loading={false} scanning={false} onScan={() => {}} />);
    expect(screen.getByRole('button', { name: /Scan Odoo Sources/i })).toBeDisabled();
  });

  it('shows the generic notice that PRJ samples are not fixed logic', () => {
    render(<OdooSourceMapPanel data={makeSourceMap()} loading={false} scanning={false} onScan={() => {}} />);
    expect(screen.getByText(/not fixed logic/i)).toBeInTheDocument();
  });
});
