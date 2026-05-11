import {
  useEffect,
  useId,
  useRef,
  type KeyboardEvent,
  type ReactNode,
} from 'react';
import { createPortal } from 'react-dom';

import { Button } from './Button';
import { closeIcon as CloseIcon } from './icons';

export interface ModalProps {
  isOpen: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
  actions?: ReactNode;
  width?: 'default' | 'wide';
  closeOnBackdrop?: boolean;
  closeOnEscape?: boolean;
}

const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(focusableSelector),
  ).filter(
    (element) =>
      !element.hasAttribute('disabled') && element.offsetParent !== null,
  );
}

export function Modal({
  isOpen,
  title,
  children,
  onClose,
  actions,
  width = 'default',
  closeOnBackdrop = true,
  closeOnEscape = true,
}: ModalProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    previousFocusRef.current = document.activeElement as HTMLElement | null;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    window.setTimeout(() => {
      const focusable = panelRef.current
        ? getFocusableElements(panelRef.current)
        : [];
      (focusable[0] ?? panelRef.current)?.focus();
    }, 0);

    return () => {
      document.body.style.overflow = originalOverflow;
      previousFocusRef.current?.focus();
    };
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape' && closeOnEscape) {
      event.preventDefault();
      onClose();
      return;
    }

    if (event.key !== 'Tab' || !panelRef.current) {
      return;
    }

    const focusable = getFocusableElements(panelRef.current);
    if (focusable.length === 0) {
      event.preventDefault();
      panelRef.current.focus();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && closeOnBackdrop) {
          onClose();
        }
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className={[
          'max-h-[85vh] rounded-md border border-border bg-surface-overlay p-6 text-text-primary shadow-md',
          'animate-[modal-in_200ms_ease-out]',
          width === 'wide' ? 'w-[640px]' : 'w-[480px]',
        ].join(' ')}
      >
        <div className="flex items-start justify-between gap-4">
          <h2 id={titleId} className="text-heading font-semibold">
            {title}
          </h2>
          <Button
            variant="ghost"
            size="compact"
            aria-label="Close dialog"
            onClick={onClose}
            icon={<CloseIcon aria-hidden="true" className="h-4 w-4" />}
            className="h-8 w-8 px-0"
          />
        </div>
        <div className="mt-4 max-h-[calc(85vh-10rem)] overflow-auto text-body">
          {children}
        </div>
        {actions ? (
          <div className="mt-6 flex justify-end gap-3">{actions}</div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
