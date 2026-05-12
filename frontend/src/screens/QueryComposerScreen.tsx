/**
 * Static Query Composer shell (Phase 1I Slice 9).
 *
 * Per `docs/design/PHASE_1I_UI_CONTRACT.md` §E.2:
 * - Form layout with no project data and no submit behavior.
 * - Query textarea is enabled for local typing only; text is ephemeral.
 * - All other inputs are disabled.
 * - No upload handler, no API calls.
 */

import { useState } from 'react';
import { Upload, ChevronDown, ChevronRight } from 'lucide-react';

import { Button } from '../components';

const OUTPUT_FORMATS = [
  { label: 'MD', checked: true },
  { label: 'DOCX', checked: false },
  { label: 'XLSX', checked: false },
  { label: 'PDF', checked: false },
  { label: 'PPTX', checked: false },
];

const FILTER_FIELDS = [
  { label: 'Contract No.', placeholder: 'e.g. CON-001' },
  { label: 'Vendor', placeholder: 'e.g. Vendor name' },
  { label: 'Date range', placeholder: 'e.g. 2026-01-01 to 2026-12-31' },
  { label: 'Document type', placeholder: 'e.g. Contract, Claim, Notice' },
];

export function QueryComposerScreen() {
  const [query, setQuery] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const maxLength = 2000;

  return (
    <div>
      {/* Page header (contract §I.3) */}
      <div className="mb-8 flex items-baseline justify-between">
        <h1 className="text-display font-semibold text-text-primary">
          Query Composer
        </h1>
        <span className="text-caption text-text-muted">
          static_scaffold — no backend data
        </span>
      </div>

      {/* Form card (contract §E.2) */}
      <div className="rounded-md border border-border bg-surface-raised p-6">
        <div className="space-y-6">
          {/* Project selector */}
          <div>
            <label className="mb-1 block text-label text-text-secondary">
              Project
            </label>
            <select
              disabled
              className="h-10 w-full cursor-not-allowed rounded-sm border border-border bg-surface-base px-3 text-body text-text-muted opacity-50"
            >
              <option>No projects available in Phase 1I</option>
            </select>
          </div>

          {/* Query textarea */}
          <div>
            <label className="mb-1 block text-label text-text-secondary">
              Management question
            </label>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              maxLength={maxLength}
              placeholder="Enter your management question…"
              rows={4}
              className="w-full min-h-[96px] resize-y rounded-sm border border-border bg-surface-base px-3 py-2 text-body text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-surface-base transition-colors duration-150"
            />
            <div className="mt-1 text-right text-caption text-text-muted">
              {query.length}/{maxLength}
            </div>
          </div>

          {/* Filters section */}
          <div>
            <button
              type="button"
              onClick={() => setFiltersOpen((v) => !v)}
              className="flex items-center gap-1 text-body font-medium text-text-secondary hover:text-text-primary transition-colors duration-150"
            >
              {filtersOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              Filters (optional)
            </button>
            {filtersOpen && (
              <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
                {FILTER_FIELDS.map((field) => (
                  <div key={field.label}>
                    <label className="mb-1 block text-label text-text-secondary">
                      {field.label}
                    </label>
                    <input
                      type="text"
                      disabled
                      placeholder={field.placeholder}
                      className="h-10 w-full cursor-not-allowed rounded-sm border border-border bg-surface-base px-3 text-body text-text-muted opacity-50"
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Upload zone */}
          <div className="flex h-32 flex-col items-center justify-center rounded-sm border border-dashed border-border bg-surface-base">
            <Upload className="h-6 w-6 text-text-muted" />
            <p className="mt-2 text-body text-text-muted">
              File upload will be available in a later phase.
            </p>
          </div>

          {/* Output formats */}
          <div>
            <span className="mb-2 block text-label text-text-secondary">
              Output formats:
            </span>
            <div className="flex flex-wrap gap-4">
              {OUTPUT_FORMATS.map((fmt) => (
                <label
                  key={fmt.label}
                  className="inline-flex cursor-not-allowed items-center gap-2 text-body text-text-muted opacity-50"
                >
                  <input
                    type="checkbox"
                    checked={fmt.checked}
                    disabled
                    className="h-4 w-4 rounded-sm border-border"
                  />
                  {fmt.label}
                </label>
              ))}
            </div>
          </div>

          {/* Action row */}
          <div className="flex justify-end">
            <Button variant="primary" disabled>
              Generate Report →
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
