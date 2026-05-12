import { Button } from '../components';
import { Menu, ChevronRight } from 'lucide-react';

export interface TopbarProps {
  currentRole?: string;
  onSidebarToggle?: () => void;
}

function roleBadgeColor(role: string): { bg: string; text: string } {
  if (role === 'admin') {
    return { bg: 'color-mix(in srgb, var(--color-text-muted) 12%, transparent)', text: 'var(--color-text-muted)' };
  }
  if (role === 'auditor') {
    return { bg: 'color-mix(in srgb, var(--color-warning) 12%, transparent)', text: 'var(--color-warning)' };
  }
  return { bg: 'color-mix(in srgb, var(--color-accent) 12%, transparent)', text: 'var(--color-accent)' };
}

export function Topbar({ currentRole = 'executive', onSidebarToggle }: TopbarProps) {
  const badge = roleBadgeColor(currentRole);

  return (
    <header className="fixed left-0 right-0 top-0 z-30 flex h-[var(--layout-topbar-height)] items-center gap-4 border-b border-border bg-surface-raised px-4">
      <Button
        variant="ghost"
        size="compact"
        onClick={onSidebarToggle}
        icon={<Menu className="h-4 w-4" aria-hidden="true" />}
        aria-label="Toggle sidebar"
      />

      <div className="flex items-center gap-2 text-label font-medium">
        <span className="text-text-primary">DecisionCenter</span>
        <ChevronRight className="h-3 w-3 text-text-muted" aria-hidden="true" />
        <span className="text-text-secondary">Dashboard</span>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <span
          className="inline-flex h-6 items-center rounded-sm px-2 text-label font-medium"
          style={{ backgroundColor: badge.bg, color: badge.text }}
        >
          {currentRole}
        </span>
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-overlay text-label font-medium text-text-secondary">
          U
        </div>
      </div>
    </header>
  );
}
