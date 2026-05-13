/**
 * Query Composer — live project dropdown + submit + upload zone (Phase 2A Slice 7).
 *
 * Per `docs/design/UI_CONTRACT_v1.md` §2.1:
 * - Project dropdown from baked fixture (backend has no list endpoint yet).
 * - Submit wired to `POST /reports/staging`.
 * - All screen states: idle, draft, submitting, queued, error, no_projects.
 * - Upload zone: local file selection, validation, preview, remove.
 *   Actual upload submission disabled — no backend endpoint.
 */

import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

import { Button, useToasts } from '../components';
import { useApi } from '../api';
import { isApiError } from '../api';
import type { OutputFormat, ReportResponse } from '../api';
import { UploadZone } from './UploadZone';
import type { UploadFile } from './UploadZone';

/** Baked from `docs/config/project_source_mapping.json` until a list endpoint exists. */
const PROJECTS = [
  { code: 'PRJ-001', contracts: ['CON-001'] },
  { code: 'PRJ-002', contracts: ['CON-002', 'CON-003'] },
];

const OUTPUT_FORMATS: { label: string; value: OutputFormat }[] = [
  { label: 'MD', value: 'md' },
  { label: 'DOCX', value: 'docx' },
  { label: 'XLSX', value: 'xlsx' },
  { label: 'PDF', value: 'pdf' },
  { label: 'PPTX', value: 'pptx' },
];

const FILTER_FIELDS = [
  { label: 'Contract No.', placeholder: 'e.g. CON-001' },
  { label: 'Vendor', placeholder: 'e.g. Vendor name' },
  { label: 'Date range', placeholder: 'e.g. 2026-01-01 to 2026-12-31' },
  { label: 'Document type', placeholder: 'e.g. Contract, Claim, Notice' },
];

type ScreenState = 'idle' | 'draft' | 'submitting' | 'queued' | 'error' | 'no_projects';

export function QueryComposerScreen() {
  const api = useApi();
  const { addToast } = useToasts();
  const [projectCode, setProjectCode] = useState('');
  const [query, setQuery] = useState('');
  const [formats, setFormats] = useState<OutputFormat[]>(['md']);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [state, setState] = useState<ScreenState>(
    PROJECTS.length === 0 ? 'no_projects' : 'idle',
  );
  const [errorMsg, setErrorMsg] = useState('');
  const maxLength = 2000;
  const queryId = 'query-composer-query';
  const projectId = 'query-composer-project';

  const canSubmit =
    state !== 'submitting' &&
    state !== 'no_projects' &&
    projectCode.trim().length > 0 &&
    query.trim().length > 0;

  async function handleSubmit() {
    if (!canSubmit) return;
    setState('submitting');
    setErrorMsg('');

    try {
      const res = await api.post<ReportResponse>('/reports/staging', {
        user_id: 'frontend-user',
        query: query.trim(),
        project_code: projectCode,
        output_formats: formats,
      });
      setState('queued');
      window.location.replace(
        '#/workspace/report/' + res.request_id + '/processing',
      );
    } catch (err) {
      setState('error');
      let message = 'An unexpected error occurred.';
      if (isApiError(err)) {
        message = err.message;
        if (err.status === 0) {
          message = 'Network error — please check your connection and try again.';
        }
      } else if (err instanceof Error) {
        message = err.message;
      }
      setErrorMsg(message);
      addToast('error', message, 'Submission failed');
    }
  }

  if (state === 'no_projects') {
    return (
      <div>
        <div className="mb-8 flex items-baseline justify-between">
          <h1 className="text-display font-semibold text-text-primary">
            Query Composer
          </h1>
          <span className="text-caption text-text-muted">live form</span>
        </div>
        <div className="rounded-md border border-border bg-surface-raised p-6 text-body text-text-secondary">
          No authorized projects for your role. Contact your administrator.
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Page header */}
      <div className="mb-8 flex items-baseline justify-between">
        <h1 className="text-display font-semibold text-text-primary">
          Query Composer
        </h1>
        <span className="text-caption text-text-muted">live form</span>
      </div>

      {/* Form card */}
      <div className="rounded-md border border-border bg-surface-raised p-6">
        <div className="space-y-6">
          {/* Project selector */}
          <div>
            <label htmlFor={projectId} className="mb-1 block text-label text-text-secondary">
              Project
            </label>
            <select
              id={projectId}
              value={projectCode}
              onChange={(e) => {
                setProjectCode(e.target.value);
                if (state === 'idle' || state === 'error') {
                  setState('draft');
                }
              }}
              className="h-10 w-full rounded-sm border border-border bg-surface-base px-3 text-body text-text-primary focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-surface-base transition-colors duration-150"
            >
              <option value="">Select a project…</option>
              {PROJECTS.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.code}
                </option>
              ))}
            </select>
          </div>

          {/* Query textarea */}
          <div>
            <label htmlFor={queryId} className="mb-1 block text-label text-text-secondary">
              Management question
            </label>
            <textarea
              id={queryId}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                if (state === 'idle' || state === 'error') {
                  setState('draft');
                }
              }}
              maxLength={maxLength}
              placeholder="Enter your management question…"
              rows={4}
              aria-describedby={`${queryId}-counter`}
              className="w-full min-h-[96px] resize-y rounded-sm border border-border bg-surface-base px-3 py-2 text-body text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-surface-base transition-colors duration-150"
            />
            <div id={`${queryId}-counter`} className="mt-1 text-right text-caption text-text-muted">
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
          <UploadZone files={files} onChange={setFiles} />

          {/* Output formats */}
          <div>
            <span className="mb-2 block text-label text-text-secondary">
              Output formats:
            </span>
            <div className="flex flex-wrap gap-4">
              {OUTPUT_FORMATS.map((fmt) => (
                <label
                  key={fmt.label}
                  className="inline-flex items-center gap-2 text-body text-text-secondary"
                >
                  <input
                    type="checkbox"
                    checked={formats.includes(fmt.value)}
                    onChange={(e) => {
                      setFormats((prev) =>
                        e.target.checked
                          ? [...prev, fmt.value]
                          : prev.filter((f) => f !== fmt.value),
                      );
                    }}
                    className="h-4 w-4 rounded-sm border-border"
                  />
                  {fmt.label}
                </label>
              ))}
            </div>
          </div>

          {/* Error banner */}
          {state === 'error' && errorMsg && (
            <div role="alert" className="rounded-sm border border-error bg-error/10 p-3 text-body text-error">
              {errorMsg}
            </div>
          )}

          {/* Action row */}
          <div className="flex justify-end">
            <Button
              variant="primary"
              disabled={!canSubmit}
              isLoading={state === 'submitting'}
              onClick={handleSubmit}
            >
              {state === 'submitting' ? 'Submitting…' : 'Generate Report →'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
