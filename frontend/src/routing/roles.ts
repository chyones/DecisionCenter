/**
 * Canonical RBAC roles — Phase 1I.
 *
 * Mirrors `docs/security/rbac_matrix.md` and
 * `docs/design/PHASE_1I_UI_CONTRACT.md` §F exactly. The 9 role identifiers
 * are locked; no additional roles may be introduced without a spec change.
 */
export const ROLES = [
  'executive',
  'project_manager',
  'finance',
  'commercial',
  'document_control',
  'procurement',
  'legal',
  'auditor',
  'admin',
] as const;

export type Role = (typeof ROLES)[number];

/** Business roles that may access the User Chat Workspace (with exceptions). */
export const BUSINESS_ROLES: Role[] = [
  'executive',
  'project_manager',
  'finance',
  'commercial',
  'document_control',
  'procurement',
  'legal',
];

/** Type guard / predicate: is the role a business role? */
export function isBusinessRole(role: Role): boolean {
  return BUSINESS_ROLES.includes(role);
}
