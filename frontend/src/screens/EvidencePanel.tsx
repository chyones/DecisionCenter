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

import { useEffect, useRef, useState } from 'react';
import { FileText, Mail, Filter, Copy, FolderOpen } from 'lucide-react';

import { SlideInPanel, Button } from '../components';
import type { EvidencePanelEntry } from '../api';

export interface EvidencePanelProps {
  isOpen: boolean;
  onClose: () => void;
  evidence: EvidencePanelEntry[];
  highlightedEvidenceId?: string | null;
}

const SOURCE_TYPES = ['All', 'SharePoint', 'Odoo', 'Email', 'ownCloud'];
const CONFIDENCE_LEVELS = ['All', 'High', 'Medium', 'Low'];

export function EvidencePanel({
  isOpen,
  onClose,
  evidence,
  highlightedEvidenceId,
}: EvidencePanelProps) {
  const [sourceFilter, setSourceFilter] = useState('All');
  const [confidenceFilter, setConfidenceFilter] = useState('All');
  const refs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    if (!isOpen || !highlightedEvidenceId) return;
    window.setTimeout(() => {
      refs.current[highlightedEvidenceId]?.scrollIntoView({
        block: 'center',
        behavior: 'smooth',
      });
    }, 0);
  }, [highlightedEvidenceId, isOpen]);

  const filtered = evidence.filter((entry) => {
    const sourceOk =
      sourceFilter === 'All' ||
      entry.source_type.toLowerCase() === sourceFilter.toLowerCase();
    const confidenceOk =
      confidenceFilter === 'All' ||
      entry.confidence.toLowerCase() === confidenceFilter.toLowerCase();
    return sourceOk && confidenceOk;
  });

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
              className="h-8 rounded-sm border border-border bg-surface-base px-2 text-label text-text-secondary"
            >
              {SOURCE_TYPES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <select
              value={confidenceFilter}
              onChange={(e) => setConfidenceFilter(e.target.value)}
              className="h-8 rounded-sm border border-border bg-surface-base px-2 text-label text-text-secondary"
            >
              {CONFIDENCE_LEVELS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="flex flex-col items-center py-8 text-center">
            <FolderOpen className="h-8 w-8 text-text-muted" aria-hidden="true" />
            <p className="mt-2 text-body text-text-secondary">
              No evidence available.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((entry) => {
              const isEmail = entry.source_type.toLowerCase() === 'email';
              const highlighted = entry.evidence_id === highlightedEvidenceId;
              return (
                <div
                  key={entry.evidence_id}
                  ref={(node) => {
                    refs.current[entry.evidence_id] = node;
                  }}
                  className={[
                    'rounded-sm border bg-surface-base p-3 transition-colors',
                    highlighted ? 'border-accent bg-accent/10' : 'border-border',
                  ].join(' ')}
                >
                  <div className="flex items-start gap-2">
                    {isEmail ? (
                      <Mail className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
                    ) : (
                      <FileText className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
                    )}
                    <div className="min-w-0 space-y-1">
                      <p className="text-body font-medium text-text-primary">
                        [{entry.citation_label}] {entry.title}
                      </p>
                      <p className="text-caption text-text-secondary">
                        Source: {entry.source_type}
                      </p>
                      {entry.timestamp && (
                        <p className="text-caption text-text-secondary">
                          Date: {entry.timestamp}
                        </p>
                      )}
                      <p className="text-caption text-text-secondary">
                        Confidence: {entry.confidence}
                      </p>
                      <p className="flex items-center gap-1 text-caption text-text-secondary">
                        Hash: …{entry.hash_short}
                        <Button
                          variant="ghost"
                          size="compact"
                          disabled
                          className="h-6 px-1"
                          icon={<Copy className="h-3 w-3" aria-hidden="true" />}
                          aria-label="Copy hash"
                        />
                      </p>
                      <p className="text-caption text-text-muted">
                        {entry.excerpt}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </SlideInPanel>
  );
}
