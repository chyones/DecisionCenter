/**
 * Production login gate — Phase 2D Slice 2.
 *
 * Rendered only when `productionAuthEnabled` (inside `<MsalProvider>`). Shows a
 * Microsoft sign-in screen until the user authenticates, then resolves the
 * caller's canonical role from `GET /me` before rendering the app. Server-side
 * RBAC remains authoritative regardless of the role surfaced here.
 */
import { useEffect, useState, type ReactNode } from 'react';
import { useIsAuthenticated, useMsal } from '@azure/msal-react';

import { useApi } from '../api';
import { useRole } from '../routing';
import type { Role } from '../routing';
import { tokenScopes } from './msalConfig';

interface MeResponse {
  user_id_hash: string;
  role: string;
}

export function LoginGate({ children }: { children: ReactNode }) {
  const isAuthenticated = useIsAuthenticated();
  const { instance } = useMsal();
  const { setRole } = useRole();
  const api = useApi();
  const [roleLoaded, setRoleLoaded] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;
    void (async () => {
      try {
        const me = await api.get<MeResponse>('/me');
        if (!cancelled) setRole(me.role as Role);
      } finally {
        if (!cancelled) setRoleLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, api, setRole]);

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-surface-base">
        <h1 className="text-h2 font-semibold text-text-primary">DecisionCenter</h1>
        <p className="text-body text-text-secondary">
          Sign in with your Microsoft account to continue.
        </p>
        <button
          type="button"
          onClick={() => void instance.loginRedirect({ scopes: tokenScopes })}
          className="rounded-md bg-accent px-4 py-2 text-label font-medium text-text-primary"
        >
          Sign in with Microsoft
        </button>
      </div>
    );
  }

  if (!roleLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-base">
        <p className="text-body text-text-secondary">Loading your workspace…</p>
      </div>
    );
  }

  return <>{children}</>;
}
