import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';

import { loadingIcon as LoadingIcon } from './icons';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
export type ButtonSize = 'compact' | 'default';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: ReactNode;
  isLoading?: boolean;
}

const variantClasses = {
  primary:
    'border-transparent bg-accent text-text-primary shadow-sm hover:brightness-110',
  secondary:
    'border-border bg-surface-raised text-text-primary hover:bg-surface-overlay',
  danger:
    'border-transparent bg-error text-text-primary shadow-sm hover:brightness-110',
  ghost:
    'border-transparent bg-transparent text-text-secondary hover:bg-text-secondary/10',
} as const satisfies Record<ButtonVariant, string>;

const sizeClasses = {
  compact: 'h-8 px-3 text-label',
  default: 'h-10 px-4 text-body',
} as const satisfies Record<ButtonSize, string>;

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      variant = 'secondary',
      size = 'default',
      icon,
      isLoading = false,
      disabled,
      className,
      children,
      type = 'button',
      ...props
    },
    ref,
  ) {
    const isDisabled = disabled || isLoading;
    const iconSlot = isLoading ? (
      <LoadingIcon aria-hidden="true" className="h-4 w-4 animate-spin" />
    ) : (
      icon
    );

    return (
      <button
        {...props}
        ref={ref}
        type={type}
        disabled={isDisabled}
        aria-busy={isLoading || undefined}
        className={[
          'inline-flex min-h-8 items-center justify-center gap-1 rounded-sm border font-medium',
          'transition-[background-color,border-color,filter,transform] duration-100',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface-base',
          'active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:brightness-100',
          sizeClasses[size],
          variantClasses[variant],
          className,
        ]
          .filter(Boolean)
          .join(' ')}
      >
        {iconSlot ? (
          <span className="inline-flex h-4 w-4 shrink-0">{iconSlot}</span>
        ) : null}
        {children}
      </button>
    );
  },
);
