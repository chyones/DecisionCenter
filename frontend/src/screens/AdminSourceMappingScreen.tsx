/**
 * Static Source Mapping — read-only view (Phase 1I Slice 8).
 *
 * Per `docs/design/PHASE_1I_UI_CONTRACT.md` §E.8:
 * - Two-column layout: project list (280px) + metadata panel.
 * - Data baked from `docs/config/project_source_mapping.example.json`.
 * - No credentials. No editor. No API call.
 */

import { useState } from 'react';

import { StatusPill } from '../components';

interface ProjectMapping {
  projectCode: string;
  sharepointSiteId: string;
  sharepointDriveId: string;
  sharepointRootPath: string;
  owncloudBasePath: string;
  sharedMailboxes: string[];
  documentControlMailbox: string;
  odooProjectModel: string;
  odooCostModel: string;
  odooProjectExternalId: string;
  contractNumbers: string[];
}

/** Baked static fixture from `docs/config/project_source_mapping.example.json`. */
const PROJECTS: ProjectMapping[] = [
  {
    projectCode: 'PRJ-001',
    sharepointSiteId: 'example-site-id',
    sharepointDriveId: 'example-drive-id',
    sharepointRootPath: '/Projects/PRJ-001',
    owncloudBasePath: '/Projects/PRJ-001',
    sharedMailboxes: ['project-prj-001@example.com'],
    documentControlMailbox: 'doc-control@example.com',
    odooProjectModel: 'project.project',
    odooCostModel: 'account.analytic.line',
    odooProjectExternalId: 'PRJ-001',
    contractNumbers: ['CON-001'],
  },
];

const METADATA_ROWS: { key: string; getValue: (p: ProjectMapping) => string }[] = [
  { key: 'Project Code', getValue: (p) => p.projectCode },
  { key: 'SharePoint Site ID', getValue: (p) => p.sharepointSiteId },
  { key: 'SharePoint Drive ID', getValue: (p) => p.sharepointDriveId },
  { key: 'SharePoint Root Path', getValue: (p) => p.sharepointRootPath },
  { key: 'ownCloud Base Path', getValue: (p) => p.owncloudBasePath },
  { key: 'Shared Mailboxes', getValue: (p) => p.sharedMailboxes.join(', ') },
  { key: 'Document Control Mailbox', getValue: (p) => p.documentControlMailbox },
  { key: 'Odoo Project Model', getValue: (p) => p.odooProjectModel },
  { key: 'Odoo Cost Model', getValue: (p) => p.odooCostModel },
  { key: 'Odoo Project External ID', getValue: (p) => p.odooProjectExternalId },
  { key: 'Contract Numbers', getValue: (p) => p.contractNumbers.join(', ') },
];

export function AdminSourceMappingScreen() {
  const [selected, setSelected] = useState<string>(PROJECTS[0].projectCode);
  const activeProject = PROJECTS.find((p) => p.projectCode === selected)!;

  return (
    <div>
      {/* Page header (contract §I.3) */}
      <div className="mb-8 flex items-baseline justify-between">
        <h1 className="text-display font-semibold text-text-primary">
          Project Source Mapping
        </h1>
        <span className="text-caption text-text-muted">
          static_scaffold — no backend data
        </span>
      </div>

      {/* Subheader (contract §E.8) */}
      <p className="mb-6 text-body text-text-secondary">
        Read-only view of the mapping shape. No credentials are shown.
      </p>

      {/* Two-column card (contract §E.8) */}
      <div className="flex overflow-hidden rounded-md border border-border bg-surface-raised">
        {/* Left column — project list (280px) */}
        <div className="w-[280px] shrink-0 border-r border-border">
          <div className="h-10 border-b border-border bg-surface-base px-3 py-2 text-label font-medium text-text-secondary">
            Projects
          </div>
          <div className="divide-y divide-border">
            {PROJECTS.map((project) => {
              const isActive = project.projectCode === selected;
              return (
                <button
                  key={project.projectCode}
                  type="button"
                  onClick={() => setSelected(project.projectCode)}
                  className={[
                    'flex h-9 w-full items-center justify-between px-3 py-2 text-left transition-colors duration-150',
                    isActive
                      ? 'border-l-2 border-accent bg-accent/[0.08]'
                      : 'border-l-2 border-transparent hover:bg-surface-overlay',
                  ].join(' ')}
                >
                  <span className="font-mono text-mono text-text-primary">
                    {project.projectCode}
                  </span>
                  <StatusPill status="connected" label="Complete" />
                </button>
              );
            })}
          </div>
        </div>

        {/* Right column — metadata panel */}
        <div className="min-w-0 flex-1 p-6">
          {METADATA_ROWS.map((row) => (
            <div
              key={row.key}
              className="flex h-9 items-center gap-3"
            >
              <span className="min-w-[140px] shrink-0 text-right text-label text-text-secondary">
                {row.key}
              </span>
              <span className="min-w-0 flex-1 truncate text-body text-text-primary">
                {row.getValue(activeProject)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
