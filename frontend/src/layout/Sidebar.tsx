import {
  LayoutDashboard,
  FileText,
  Settings,
  Shield,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  icon: React.ElementType;
  label: string;
  active?: boolean;
}

const navItems: NavItem[] = [
  { icon: LayoutDashboard, label: 'Dashboard', active: true },
  { icon: FileText, label: 'Reports', active: false },
  { icon: Shield, label: 'Permissions', active: false },
  { icon: Settings, label: 'Settings', active: false },
];

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const width = collapsed
    ? 'var(--layout-sidebar-rail-width)'
    : 'var(--layout-sidebar-width)';

  return (
    <aside
      className="fixed bottom-0 left-0 top-[var(--layout-topbar-height)] z-20 flex flex-col border-r border-border bg-surface-raised transition-[width] duration-200 ease-linear"
      style={{ width }}
    >
      <nav className="flex-1 overflow-y-auto py-2">
        {navItems.map((item) => {
          const isActive = item.active;
          const activeClasses = isActive
            ? collapsed
              ? 'bg-accent/10 text-accent'
              : 'border-l-2 border-accent bg-accent/10 text-accent'
            : 'border-l-2 border-transparent text-text-secondary hover:bg-surface-overlay';

          return (
            <a
              key={item.label}
              href="#"
              onClick={(e) => e.preventDefault()}
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
