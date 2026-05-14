/**
 * Upload Zone — Phase 2A Slice 7.
 *
 * Per `docs/design/UI_CONTRACT_v1.md` §2.5 & §5:
 * - Drag-and-drop and file-picker support.
 * - Client-side validation: type, per-file size (10 MB), count (5), total size (30 MB).
 * - Preview list with filename, size, and remove action.
 * - Upload validation mirrors the backend `POST /upload` contract.
 */

import { useCallback, useRef, useState } from 'react';
import { Upload, X, FileText, AlertCircle, Info } from 'lucide-react';

import { Button } from '../components';

const ACCEPTED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/plain',
  'message/rfc822',
];

const ACCEPTED_EXTENSIONS = new Set(['.pdf', '.docx', '.xlsx', '.txt', '.msg', '.eml']);

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
const MAX_TOTAL_SIZE = 30 * 1024 * 1024; // 30 MB
const MAX_FILES = 5;

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isAccepted(file: File): boolean {
  if (ACCEPTED_TYPES.includes(file.type)) return true;
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  return ACCEPTED_EXTENSIONS.has(ext);
}

function isCAD(file: File): boolean {
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  return ['.dwg', '.dxf', '.ifc', '.rvt'].includes(ext);
}

export interface UploadFile {
  id: string;
  file: File;
  status: 'ready' | 'error';
  error?: string;
}

export interface UploadZoneProps {
  files: UploadFile[];
  onChange: (files: UploadFile[]) => void;
}

export function UploadZone({ files, onChange }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dropError, setDropError] = useState('');

  const validateAndAdd = useCallback(
    (incoming: FileList | null) => {
      setDropError('');
      if (!incoming || incoming.length === 0) return;

      const next = [...files];
      let totalSize = next.reduce((s, f) => s + f.file.size, 0);

      for (const file of Array.from(incoming)) {
        if (next.length >= MAX_FILES) {
          setDropError(`Maximum ${MAX_FILES} files allowed.`);
          break;
        }

        if (isCAD(file)) {
          setDropError('CAD files are not supported in this release. Contact your administrator.');
          continue;
        }

        if (!isAccepted(file)) {
          setDropError(`Unsupported file type: ${file.name}`);
          continue;
        }

        if (file.size > MAX_FILE_SIZE) {
          setDropError(`${file.name} exceeds 10 MB limit.`);
          continue;
        }

        if (totalSize + file.size > MAX_TOTAL_SIZE) {
          setDropError('Total upload size would exceed 30 MB.');
          break;
        }

        next.push({
          id: `${file.name}-${file.size}-${Date.now()}`,
          file,
          status: 'ready',
        });
        totalSize += file.size;
      }

      onChange(next);
    },
    [files, onChange],
  );

  function removeFile(id: string) {
    onChange(files.filter((f) => f.id !== id));
    setDropError('');
  }

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload files. Drag files here or press Enter to browse."
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          validateAndAdd(e.dataTransfer.files);
        }}
        className={[
          'flex cursor-pointer flex-col items-center justify-center rounded-sm border border-dashed p-6 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface-base',
          isDragging
            ? 'border-accent bg-accent/10'
            : 'border-border bg-surface-base hover:bg-surface-overlay',
        ].join(' ')}
      >
        <Upload className="h-6 w-6 text-text-muted" aria-hidden="true" />
        <p className="mt-2 text-body text-text-secondary">
          Drag files here or <span className="text-accent">browse</span>
        </p>
        <p className="mt-1 text-caption text-text-muted">
          PDF · DOCX · XLSX · TXT · MSG
        </p>
        <p className="text-caption text-text-muted">
          Max 10 MB per file · Max 5 files
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => validateAndAdd(e.target.files)}
        />
      </div>

      {/* Error banner */}
      {dropError && (
        <div role="alert" className="flex items-start gap-2 rounded-sm border border-error bg-error/10 p-3">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-error" aria-hidden="true" />
          <p className="text-body text-error">{dropError}</p>
        </div>
      )}

      {/* File list */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((f) => (
            <div
              key={f.id}
              className="flex items-center gap-3 rounded-sm border border-border bg-surface-base px-3 py-2"
            >
              <FileText className="h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-body text-text-primary">{f.file.name}</p>
                <p className="text-caption text-text-muted">{formatSize(f.file.size)}</p>
              </div>
              <Button
                variant="ghost"
                size="compact"
                className="h-8 w-8 px-0"
                onClick={() => removeFile(f.id)}
                icon={<X className="h-4 w-4" />}
                aria-label={`Remove ${f.file.name}`}
              />
            </div>
          ))}
        </div>
      )}

      {/* Info footer */}
      <div className="flex items-start gap-2 text-caption text-text-muted">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <p>
          These files are used as context only. They are not added to company
          evidence sources. Files are deleted per the retention policy.
        </p>
      </div>

      <div className="flex items-start gap-2 rounded-sm border border-border bg-surface-raised p-3">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
        <p className="text-body text-text-secondary">
          Files are validated here before they are attached to a report request.
        </p>
      </div>
    </div>
  );
}
