import { useId, useState, type ReactNode } from 'react';

import { Button, type ButtonVariant } from './Button';
import { warningIcon as WarningIcon } from './icons';
import { Modal } from './Modal';

export interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  children: ReactNode;
  confirmationText: string;
  confirmLabel: string;
  cancelLabel?: string;
  variant?: Extract<ButtonVariant, 'primary' | 'danger'>;
  onClose: () => void;
  onConfirm?: () => void | Promise<void>;
}

export function ConfirmDialog({
  isOpen,
  title,
  children,
  confirmationText,
  confirmLabel,
  cancelLabel = 'Cancel',
  variant = 'danger',
  onClose,
  onConfirm,
}: ConfirmDialogProps) {
  const inputId = useId();
  const helperId = useId();
  const [typedValue, setTypedValue] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const matches = typedValue === confirmationText;
  const showMismatch = typedValue.length > 0 && !matches;

  async function handleConfirm() {
    if (!matches || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    try {
      await onConfirm?.();
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      title={title}
      onClose={onClose}
      width="wide"
      closeOnBackdrop={false}
      actions={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            {cancelLabel}
          </Button>
          <Button
            variant={variant}
            icon={
              variant === 'primary' ? (
                <WarningIcon aria-hidden="true" className="h-4 w-4" />
              ) : undefined
            }
            disabled={!matches}
            isLoading={isSubmitting}
            onClick={handleConfirm}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>{children}</div>
        <div>
          <label
            htmlFor={inputId}
            className="block text-label font-medium text-text-primary"
          >
            Type "{confirmationText}" to confirm
          </label>
          <input
            id={inputId}
            value={typedValue}
            onChange={(event) => setTypedValue(event.target.value)}
            aria-describedby={helperId}
            className={[
              'mt-2 h-10 w-full rounded-sm border bg-surface-base px-3 text-body text-text-primary',
              'focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-surface-base',
              showMismatch ? 'border-error' : 'border-border',
            ].join(' ')}
          />
          <p
            id={helperId}
            className={[
              'mt-2 text-caption',
              showMismatch ? 'text-error' : 'text-text-secondary',
            ].join(' ')}
          >
            {showMismatch
              ? 'Confirmation does not match.'
              : 'The confirm action remains disabled until the text matches exactly.'}
          </p>
        </div>
      </div>
    </Modal>
  );
}
