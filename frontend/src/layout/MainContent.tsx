import type { ReactNode } from 'react';

export interface MainContentProps {
  children?: ReactNode;
}

export function MainContent({ children }: MainContentProps) {
  return (
    <div className="mx-auto w-full max-w-[var(--layout-main-max-width)] px-6 py-8">
      {children}
    </div>
  );
}
