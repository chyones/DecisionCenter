import { useEffect, useRef, type ReactNode } from 'react';

import { Button } from './Button';
import { closeIcon as CloseIcon } from './icons';

export interface SlideInPanelProps {
  isOpen: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
  ariaLabel?: string;
}

const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

export function SlideInPanel({
  isOpen,
  title,
  children,
  onClose,
  ariaLabel = 'Detail panel',
}: SlideInPanelProps) {
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!isOpen || !panelRef.current) {
      return;
    }

    const firstFocusable =
      panelRef.current.querySelector<HTMLElement>(focusableSelector);
    (firstFocusable ?? panelRef.current).focus();
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <>
      <div
        className="fixed inset-x-0 bottom-0 top-[var(--layout-topbar-height)] z-40 bg-black/40"
        onMouseDown={(event) => {
          if (event.target === event.currentTarget) {
            onClose();
          }
        }}
      />
      <aside
        ref={panelRef}
        aria-label={ariaLabel}
        tabIndex={-1}
        className="fixed bottom-0 right-0 top-[var(--layout-topbar-height)] z-50 flex w-[var(--layout-detail-panel-width)] animate-[panel-in_250ms_ease-out] flex-col border-l border-border bg-surface-raised text-text-primary shadow-lg focus:outline-none"
      >
        <header className="flex items-center justify-between gap-4 border-b border-border p-4">
          <h2 className="text-heading font-semibold">{title}</h2>
          <Button
            variant="ghost"
            size="compact"
            aria-label="Close panel"
            onClick={onClose}
            icon={<CloseIcon aria-hidden="true" className="h-4 w-4" />}
            className="h-8 w-8 px-0"
          />
        </header>
        <div className="flex-1 overflow-auto p-4 text-body">{children}</div>
      </aside>
    </>
  );
}
