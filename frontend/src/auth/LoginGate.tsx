/**
 * Production login gate — Phase 2D Slice 2.
 *
 * Rendered only when `productionAuthEnabled` (inside `<MsalProvider>`). Shows a
 * Microsoft sign-in screen until the user authenticates, then resolves the
 * caller's canonical role before rendering the app. Server-side RBAC remains
 * authoritative regardless of the role surfaced here.
 *
 * Role source: prefer `GET /me`; fall back to `GET /workspace/context` (same
 * server-validated role, already proxied) when /me is unreachable or mis-routed.
 * On failure we surface the real error instead of silently defaulting to
 * `executive`. For auth (401) failures we also decode and show the access
 * token's non-secret diagnostic claims (iss/aud/ver/roles) — never the token
 * itself — so issuer/audience/version mismatches can be diagnosed without
 * browser devtools.
 *
 * Direct-access / deep-link: the hash fragment before `loginRedirect` is saved
 * to sessionStorage and restored after role resolution so the user lands on the
 * page they originally requested rather than the default landing.
 */
import { useEffect, useState, type ReactNode } from 'react';
import { useIsAuthenticated, useMsal } from '@azure/msal-react';

import { useApi, ApiError } from '../api';
import { useRole } from '../routing';
import type { Role } from '../routing';
import type { ApiClient } from '../api';
import { acquireAccessToken, tokenScopes } from './msalConfig';

interface MeResponse {
  user_id_hash: string;
  role: string;
}

function isValidRole(value: unknown): value is string {
  return typeof value === 'string' && value !== '';
}

/** Decode a JWT's payload claims (no signature check). Returns null on failure. */
function decodeJwtClaims(token: string): Record<string, unknown> | null {
  try {
    const part = token.split('.')[1];
    if (!part) return null;
    const b64 = part.replace(/-/g, '+').replace(/_/g, '/');
    const json = decodeURIComponent(
      atob(b64)
        .split('')
        .map((c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0'))
        .join(''),
    );
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Build a non-secret one-line diagnostic from the current access token. */
async function tokenDiagnostic(): Promise<string> {
  try {
    const token = await acquireAccessToken();
    const c = decodeJwtClaims(token);
    if (!c) return '';
    const tenant = import.meta.env.VITE_ENTRA_TENANT_ID ?? '';
    const expectedIss = `https://login.microsoftonline.com/${tenant}/v2.0`;
    const roles = Array.isArray(c.roles) ? (c.roles as unknown[]).join(',') : '(none)';
    return (
      ` [token iss=${String(c.iss ?? '?')} ; ver=${String(c.ver ?? '?')} ; ` +
      `aud=${String(c.aud ?? '?')} ; roles=${roles} ; expected iss=${expectedIss}]`
    );
  } catch {
    return '';
  }
}

/**
 * Resolve the caller's canonical role. Prefer /me; fall back to
 * /workspace/context (same server-validated role, already proxied) when /me is
 * missing, errors, or returns a non-JSON body. Throws if neither yields a role.
 */
async function resolveRole(api: ApiClient): Promise<string> {
  try {
    const me = await api.get<MeResponse>('/me');
    if (me && isValidRole(me.role)) return me.role;
  } catch {
    // /me errored (e.g. 4xx/5xx) — fall through to the workspace context.
  }
  const ctx = await api.get<{ role: string }>('/workspace/context');
  if (ctx && isValidRole(ctx.role)) return ctx.role;
  throw new Error('Neither /me nor /workspace/context returned a valid role.');
}

/** Pop the hash saved before a login redirect, if any. */
function popSavedHash(): string | null {
  const saved = sessionStorage.getItem('dc-pre-login-hash');
  if (saved) sessionStorage.removeItem('dc-pre-login-hash');
  return saved || null;
}

export function LoginGate({ children }: { children: ReactNode }) {
  const isAuthenticated = useIsAuthenticated();
  const { instance } = useMsal();
  const { setRole } = useRole();
  const api = useApi();
  const [roleLoaded, setRoleLoaded] = useState(false);
  const [roleError, setRoleError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;
    void (async () => {
      try {
        const role = await resolveRole(api);
        if (!cancelled) {
          setRole(role as Role);
          const savedHash = popSavedHash();
          if (savedHash) window.location.hash = savedHash.replace(/^#/, '');
        }
      } catch (err) {
        if (cancelled) return;
        const reason =
          err instanceof ApiError
            ? `${err.status}: ${err.message}`
            : err instanceof Error
              ? err.message
              : 'Unknown error';
        // For auth failures, append the non-secret token claims to pinpoint
        // issuer/audience/version mismatches.
        const diag =
          err instanceof ApiError && err.status === 401
            ? await tokenDiagnostic()
            : '';
        if (cancelled) return;
        setRoleError(
          `Could not determine your access role (${reason}).${diag} ` +
            'Please contact your administrator.',
        );
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
          onClick={() => {
            const hash = window.location.hash;
            if (hash && hash !== '#' && hash !== '#/') {
              sessionStorage.setItem('dc-pre-login-hash', hash);
            }
            void instance.loginRedirect({ scopes: tokenScopes });
          }}
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

  if (roleError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-surface-base px-6 text-center">
        <h1 className="text-h2 font-semibold text-text-primary">Sign-in problem</h1>
        <p className="max-w-2xl break-words text-body text-text-secondary">{roleError}</p>
        <button
          type="button"
          onClick={() => void instance.logoutRedirect({ postLogoutRedirectUri: window.location.origin })}
          className="rounded-md bg-accent px-4 py-2 text-label font-medium text-text-primary"
        >
          Sign out and try again
        </button>
      </div>
    );
  }

  return <>{children}</>;
}
