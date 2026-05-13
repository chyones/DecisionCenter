/**
 * Evidence Panel — Phase 2A Slice 5.
 *
 * Per `docs/design/UI_CONTRACT_v1.md` §2.3:
 * - Slide-in from Report View.
 * - Evidence entries: source label, source type, confidence score, truncated hash.
 * - Email excerpts read-only; document excerpts copyable.
 * - Filter by source type and confidence.
 *
 * Limitation: `GET /reports/{id}` and evidence endpoints do not exist at backend
 * HEAD. The panel renders a contract-correct structural shell with empty-state
 * messaging. No backend data is invented.
 */

import { useState } from 'react';
import { FileText, Mail, Filter, Copy, FolderOpen } from 'lucide-react';

import { SlideInPanel, Button } from '../components';

export interface EvidencePanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const SOURCE_TYPES = ['All', 'SharePoint', 'Odoo', 'Email', 'ownCloud'];
const CONFIDENCE_LEVELS = ['All', 'High', 'Medium', 'Low'];

export function EvidencePanel({ isOpen, onClose }: EvidencePanelProps) {
  const [sourceFilter, setSourceFilter] = useState('All');
  const [confidenceFilter, setConfidenceFilter] = useState('All');

  return (
    <SlideInPanel isOpen={isOpen} title="Evidence" onClose={onClose}>
      <div className="space-y-6">
        {/* Filters */}
        <div className="space-y-2">
          <div className="flex items-center gap-1 text-label text-text-secondary">
            <Filter className="h-3.5 w-3.5" />
            Filters
          </div>
          <div className="flex flex-col gap-2">
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              disabled
              className="h-8 cursor-not-allowed rounded-sm border border-border bg-surface-base px-2 text-label text-text-muted opacity-50"
            >
              {SOURCE_TYPES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <select
              value={confidenceFilter}
              onChange={(e) => setConfidenceFilter(e.target.value)}
              disabled
              className="h-8 cursor-not-allowed rounded-sm border border-border bg-surface-base px-2 text-label text-text-muted opacity-50"
            >
              {CONFIDENCE_LEVELS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
          <p className="text-caption text-text-muted">
            Evidence filtering requires a live backend endpoint.
          </p>
        </div>

        {/* Empty state */}
        <div className="flex flex-col items-center py-8 text-center">
          <FolderOpen className="h-8 w-8 text-text-muted" aria-hidden="true" />
          <p className="mt-2 text-body text-text-secondary">
            No evidence available.
          </p>
          <p className="mt-1 text-caption text-text-muted">
            Evidence Panel requires a live report detail endpoint that is not yet
            available.
          </p>
        </div>

        {/* Contract-correct entry anatomy example (static, non-interactive) */}
        <div className="border-t border-border pt-4">
          <p className="mb-3 text-label font-medium text-text-secondary">
            Evidence entry format:
          </p>
          <div className="space-y-3 rounded-sm border border-border bg-surface-base p-3 opacity-60">
            <div className="flex items-start gap-2">
              <FileText className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
              <div className="space-y-1">
                <p className="text-body font-medium text-text-primary">
                  [1] CON-001 — Payment Schedule
                </p>
                <p className="text-caption text-text-secondary">
                  Source: Odoo · account.analytic.line
                </p>
                <p className="text-caption text-text-secondary">
                  Date: 2026-04-30
                </p>
                <p className="text-caption text-text-secondary">
                  Confidence: High (0.91)
                </p>
                <p className="flex items-center gap-1 text-caption text-text-secondary">
                  Hash: …c12d4e7f
                  <Button
                    variant="ghost"
                    size="compact"
                    disabled
                    className="h-6 px-1"
                    icon={<Copy className="h-3 w-3" />}
                  />
                </p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <Mail className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
              <div className="space-y-1">
                <p className="text-body font-medium text-text-primary">
                  [2] Re: Contract amendment
                </p>
                <p className="text-caption text-text-secondary">
                  Source: Email · shared mailbox
                </p>
                <p className="text-caption text-text-secondary">
                  Confidence: Medium (0.72)
                </p>
                <p className="text-caption text-text-muted">
                  Email excerpts are read-only.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </SlideInPanel>
  );
}
