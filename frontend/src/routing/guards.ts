import type { Role } from './roles';

/**
 * Client-side route guards — UX only.
 *
 * Per `docs/design/PHASE_1I_UI_CONTRACT.md` §F.2:
 * "The client guard must route denied access to a static forbidden state or
 * role-appropriate landing. It must not create or weaken backend authorization."
 *
 * Server-side 403 remains the authoritative enforcement layer.
 *
 * Owner-operator override (`docs/execution/SPEC_CHANGE_2026-05-31_owner_operator_model.md`):
 * `admin` is a full owner (generate/approve/read) PLUS system operator, so the
 * original §F.2 rule "admin is blocked from all /workspace/* routes" no longer
 * applies — admin may use the report workspace like any owner. This guard is
 * cosmetic; the backend already authorizes admin on the workspace/report flow.
 */

/** Default landing path for each canonical role (contract §F.1). */
export function getDefaultLanding(role: Role): string {
  if (role === 'admin') return '/admin/dashboard';
  if (role === 'auditor') return '/workspace/reports';
  return '/workspace/new';
}

/**
 * Is `path` accessible to `role` in the client-side route matrix?
 *
 * Rules (contract §F.2, as amended by the owner-operator SPEC_CHANGE):
 * - Business roles are blocked from all `/admin/*` routes (admin-only).
 * - `auditor` is blocked from `/workspace/new` and any submit/processing action.
 * - `admin` may access `/workspace/*` (full owner) in addition to `/admin/*`.
 */
export function isRouteAllowed(role: Role, path: string): boolean {
  // Root redirect and explicit forbidden page are always reachable.
  if (path === '/' || path === '/403') return true;

  if (path.startsWith('/admin')) {
    return role === 'admin';
  }

  if (path.startsWith('/workspace')) {
    // Owner-operator model (SPEC_CHANGE 2026-05-31): admin is a full owner and
    // is NOT blocked from the workspace. Only auditor keeps workspace limits.
    if (path === '/workspace/new' && role === 'auditor') return false;
    if (path.startsWith('/workspace/report/') && path.endsWith('/processing') && role === 'auditor') {
      return false;
    }
    return true;
  }

  return false;
}
