import { useEffect, useRef, type ReactNode } from 'react';

import { colorVar } from '../tokens';
import { Button } from './Button';
import { closeIcon as CloseIcon, statusIconMap } from './icons';

export type ToastTone = 'info' | 'success' | 'warning' | 'error';

export interface ToastMessage {
  id: string;
  tone: ToastTone;
  title?: string;
  body: ReactNode;
}

export interface ToastProps extends ToastMessage {
  onDismiss: (id: string) => void;
}

export interface ToastViewportProps {
  toasts: readonly ToastMessage[];
  onDismiss: (id: string) => void;
}

const toneConfig = {
  info: {
    color: 'accent',
    icon: statusIconMap['circle-dashed'],
    role: 'status',
    timeoutMs: 5000,
  },
  success: {
    color: 'success',
    icon: statusIconMap['circle-check'],
    role: 'status',
    timeoutMs: 5000,
  },
  warning: {
    color: 'warning',
    icon: statusIconMap['triangle-alert'],
    role: 'alert',
    timeoutMs: 8000,
  },
  error: {
    color: 'error',
    icon: statusIconMap['x-circle'],
    role: 'alert',
    timeoutMs: 8000,
  },
} as const;

export function Toast({ id, tone, title, body, onDismiss }: ToastProps) {
  const config = toneConfig[tone];
  const Icon = config.icon;
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    timeoutRef.current = window.setTimeout(
      () => onDismiss(id),
      config.timeoutMs,
    );
    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, [config.timeoutMs, id, onDismiss]);

  function pauseTimer() {
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }

  function resumeTimer() {
    if (timeoutRef.current === null) {
      timeoutRef.current = window.setTimeout(
        () => onDismiss(id),
        config.timeoutMs,
      );
    }
  }

  return (
    <article
      role={config.role}
      onMouseEnter={pauseTimer}
      onMouseLeave={resumeTimer}
      className="flex min-h-12 w-[360px] max-w-[calc(100vw-2rem)] gap-3 rounded-sm border border-border bg-surface-raised px-4 py-3 text-text-primary shadow-md"
      style={{ borderLeft: `3px solid ${colorVar(config.color)}` }}
    >
      <Icon
        aria-hidden="true"
        className="mt-0.5 h-4 w-4 shrink-0"
        style={{ color: colorVar(config.color) }}
      />
      <div className="min-w-0 flex-1">
        {title ? <p className="text-label font-medium">{title}</p> : null}
        <div className="text-caption text-text-secondary">{body}</div>
      </div>
      <Button
        variant="ghost"
        size="compact"
        aria-label="Dismiss notification"
        onClick={() => onDismiss(id)}
        icon={<CloseIcon aria-hidden="true" className="h-4 w-4" />}
        className="h-8 w-8 px-0"
      />
    </article>
  );
}

export function ToastViewport({ toasts, onDismiss }: ToastViewportProps) {
  return (
    <div
      aria-live="polite"
      className="fixed right-4 top-4 z-[60] flex max-w-[calc(100vw-2rem)] flex-col gap-2"
    >
      {toasts.slice(0, 3).map((toast) => (
        <Toast key={toast.id} {...toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
