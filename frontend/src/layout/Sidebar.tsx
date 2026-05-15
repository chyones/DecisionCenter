import {
  FilePlus,
  FileText,
  LayoutDashboard,
  Activity,
  Plug,
  Shield,
  Map,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useRole } from '../routing/RoleContext';
import { useHashPath } from '../routing/useHashPath';
import type { Role } from '../routing/roles';

export interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItemDef {
  icon: React.ElementType;
  label: string;
  path: string;
  visible: (role: Role) => boolean;
}

const navItems: NavItemDef[] = [
  // Workspace
  {
    icon: FilePlus,
    label: 'New Query',
    path: '/workspace/new',
    visible: (r) => r !== 'auditor' && r !== 'admin',
  },
  {
    icon: FileText,
    label: 'Reports',
    path: '/workspace/reports',
    visible: (r) => r !== 'admin',
  },
  // Admin
  {
    icon: LayoutDashboard,
    label: 'Dashboard',
    path: '/admin',
    visible: (r) => r === 'admin',
  },
  {
    icon: Activity,
    label: 'System Health',
    path: '/admin/health',
    visible: (r) => r === 'admin',
  },
  {
    icon: Plug,
    label: 'Connectors',
    path: '/admin/connectors',
    visible: (r) => r === 'admin',
  },
  {
    icon: Shield,
    label: 'Permissions',
    path: '/admin/permissions',
    visible: (r) => r === 'admin',
  },
  {
    icon: Map,
    label: 'Source Mapping',
    path: '/admin/source-mapping',
    visible: (r) => r === 'admin',
  },
];

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { role } = useRole();
  const path = useHashPath();

  const visibleItems = navItems.filter((item) => item.visible(role));

  const width = collapsed
    ? 'var(--layout-sidebar-rail-width)'
    : 'var(--layout-sidebar-width)';

  return (
    <aside
      className="fixed bottom-0 left-0 top-[var(--layout-topbar-height)] z-20 flex flex-col border-r border-border bg-surface-raised transition-[width] duration-200 ease-linear"
      style={{ width }}
    >
      <nav className="flex-1 overflow-y-auto py-2">
        {visibleItems.map((item) => {
          const isActive =
            path === item.path ||
            (item.path === '/workspace/reports' && path.startsWith('/workspace/report/'));
          const activeClasses = isActive
            ? collapsed
              ? 'bg-accent/10 text-accent'
              : 'border-l-2 border-accent bg-accent/10 text-accent'
            : 'border-l-2 border-transparent text-text-secondary hover:bg-surface-overlay';

          return (
            <a
              key={item.label}
              href={'#' + item.path}
              className={[
                'mx-2 flex h-9 items-center gap-2 rounded-sm px-3 text-body transition-colors duration-150',
                activeClasses,
                collapsed ? 'justify-center px-0' : '',
              ].join(' ')}
              aria-current={isActive ? 'page' : undefined}
              title={collapsed ? item.label : undefined}
            >
              <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span
                className={[
                  'truncate transition-opacity duration-150',
                  collapsed ? 'opacity-0' : 'opacity-100',
                ].join(' ')}
              >
                {item.label}
              </span>
            </a>
          );
        })}
      </nav>

      <div className="border-t border-border p-2">
        <button
          type="button"
          onClick={onToggle}
          className="flex h-9 w-full items-center justify-center rounded-sm text-text-secondary transition-colors duration-150 hover:bg-surface-overlay"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          ) : (
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          )}
          {!collapsed && <span className="ml-2 text-label">Collapse</span>}
        </button>
      </div>
    </aside>
  );
}
