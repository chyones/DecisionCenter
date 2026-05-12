import { useState, type ReactNode } from 'react';
import { Topbar } from './Topbar';
import { Sidebar } from './Sidebar';
import { MainContent } from './MainContent';
import { UnsupportedWidth } from './UnsupportedWidth';

export interface AppShellProps {
  children?: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);

  const sidebarWidth = collapsed
    ? 'var(--layout-sidebar-rail-width)'
    : 'var(--layout-sidebar-width)';

  return (
    <div className="flex h-screen w-screen">
      <Topbar onSidebarToggle={() => setCollapsed((c) => !c)} />
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />

      <div
        className="flex flex-1 flex-col transition-[margin-left] duration-200 ease-linear"
        style={{ marginLeft: sidebarWidth }}
      >
        {/* Spacer for fixed topbar */}
        <div className="h-[var(--layout-topbar-height)] shrink-0" />
        <main className="flex-1 overflow-auto bg-surface-base">
          <MainContent>{children}</MainContent>
        </main>
      </div>

      <UnsupportedWidth />
    </div>
  );
}
