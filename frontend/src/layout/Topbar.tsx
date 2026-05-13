import { Button } from '../components';
import { Menu, ChevronRight } from 'lucide-react';
import { useRole } from '../routing/RoleContext';
import { useHashPath } from '../routing/useHashPath';

export interface TopbarProps {
  onSidebarToggle?: () => void;
}

function roleBadgeColor(role: string): { bg: string; text: string } {
  if (role === 'admin') {
    return {
      bg: 'color-mix(in srgb, var(--color-text-muted) 12%, transparent)',
      text: 'var(--color-text-muted)',
    };
  }
  if (role === 'auditor') {
    return {
      bg: 'color-mix(in srgb, var(--color-warning) 12%, transparent)',
      text: 'var(--color-warning)',
    };
  }
  return {
    bg: 'color-mix(in srgb, var(--color-accent) 12%, transparent)',
    text: 'var(--color-accent)',
  };
}

function breadcrumbLabel(path: string): string {
  if (path === '/workspace/new') return 'Query Composer';
  if (path === '/workspace/reports') return 'Reports';
  if (path.startsWith('/workspace/report/') && path.endsWith('/processing')) {
    return 'Processing';
  }
  if (path.startsWith('/workspace/report/')) return 'Report View';
  if (path.startsWith('/workspace/')) return 'Workspace';
  if (path === '/admin') return 'Dashboard';
  if (path === '/admin/health') return 'System Health';
  if (path === '/admin/permissions') return 'Permissions';
  if (path === '/admin/source-mapping') return 'Source Mapping';
  if (path.startsWith('/admin/')) return 'Admin';
  if (path === '/403') return 'Forbidden';
  return 'Dashboard';
}

export function Topbar({ onSidebarToggle }: TopbarProps) {
  const { role } = useRole();
  const path = useHashPath();
  const badge = roleBadgeColor(role);
  const pageLabel = breadcrumbLabel(path);

  return (
    <header className="fixed left-0 right-0 top-0 z-30 flex h-[var(--layout-topbar-height)] items-center gap-4 border-b border-border bg-surface-raised px-4">
      <Button
        variant="ghost"
        size="compact"
        onClick={onSidebarToggle}
        icon={<Menu className="h-4 w-4" aria-hidden="true" />}
        aria-label="Toggle sidebar"
      />

      <nav
        className="flex items-center gap-2 text-label font-medium"
        aria-label="Breadcrumb"
      >
        <span className="text-text-primary">DecisionCenter</span>
        <ChevronRight className="h-3 w-3 text-text-muted" aria-hidden="true" />
        <span className="text-text-secondary">{pageLabel}</span>
      </nav>

      <div className="ml-auto flex items-center gap-3">
        <span
          className="inline-flex h-6 items-center rounded-sm px-2 text-label font-medium"
          style={{ backgroundColor: badge.bg, color: badge.text }}
        >
          {role}
        </span>
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-overlay text-label font-medium text-text-secondary">
          U
        </div>
      </div>
    </header>
  );
}
