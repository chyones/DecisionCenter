import type { Role } from './roles';

/**
 * Client-side route guards — UX only.
 *
 * Per `docs/design/PHASE_1I_UI_CONTRACT.md` §F.2:
 * "The client guard must route denied access to a static forbidden state or
 * role-appropriate landing. It must not create or weaken backend authorization."
 *
 * Server-side 403 remains the authoritative enforcement layer.
 */

/** Default landing path for each canonical role (contract §F.1). */
export function getDefaultLanding(role: Role): string {
  if (role === 'admin') return '/admin';
  if (role === 'auditor') return '/workspace/reports';
  return '/workspace/new';
}

/**
 * Is `path` accessible to `role` in the Phase 1I client-side route matrix?
 *
 * Rules (contract §F.2):
 * - Business roles are blocked from all `/admin/*` routes.
 * - `auditor` is blocked from `/workspace/new` and any submit action.
 * - `admin` is blocked from all `/workspace/*` routes.
 */
export function isRouteAllowed(role: Role, path: string): boolean {
  // Root redirect and explicit forbidden page are always reachable.
  if (path === '/' || path === '/403') return true;

  if (path.startsWith('/admin')) {
    return role === 'admin';
  }

  if (path.startsWith('/workspace')) {
    if (role === 'admin') return false;
    if (path === '/workspace/new' && role === 'auditor') return false;
    if (path.startsWith('/workspace/report/') && path.endsWith('/processing') && role === 'auditor') {
      return false;
    }
    return true;
  }

  return false;
}
