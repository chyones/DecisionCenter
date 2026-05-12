import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Role } from './roles';

interface RoleContextValue {
  role: Role;
  setRole: (role: Role) => void;
}

const RoleContext = createContext<RoleContextValue | null>(null);

export function RoleProvider({
  children,
  initialRole = 'executive',
}: {
  children: ReactNode;
  initialRole?: Role;
}) {
  const [role, setRole] = useState<Role>(initialRole);
  return (
    <RoleContext.Provider value={{ role, setRole }}>
      {children}
    </RoleContext.Provider>
  );
}

export function useRole(): RoleContextValue {
  const ctx = useContext(RoleContext);
  if (!ctx) {
    throw new Error('useRole must be used within a RoleProvider');
  }
  return ctx;
}
