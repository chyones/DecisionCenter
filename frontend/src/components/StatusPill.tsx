import type { HTMLAttributes } from 'react';

import {
  colorAlpha,
  colorVar,
  STATUS_REGISTRY,
  type StatusValue,
} from '../tokens';
import { getStatusIcon } from './icons';

export interface StatusPillProps extends HTMLAttributes<HTMLSpanElement> {
  status: StatusValue;
  label?: string;
}

export function StatusPill({
  status,
  label,
  className,
  ...props
}: StatusPillProps) {
  const definition = STATUS_REGISTRY[status];
  const Icon = getStatusIcon(status);
  const text = label ?? definition.label;

  return (
    <span
      {...props}
      aria-label={`Status: ${text}`}
      aria-live={definition.pulsing ? 'polite' : undefined}
      className={[
        'inline-flex h-6 max-h-7 min-h-6 items-center gap-1 rounded-sm px-2 text-label font-medium',
        'select-none whitespace-nowrap',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      style={{
        color: colorVar(definition.color),
        backgroundColor: colorAlpha(definition.color, 0.12),
        ...props.style,
      }}
    >
      <Icon
        aria-hidden="true"
        className={[
          'h-3.5 w-3.5 shrink-0',
          definition.pulsing ? 'animate-spin' : '',
        ]
          .filter(Boolean)
          .join(' ')}
      />
      <span>{text}</span>
    </span>
  );
}
