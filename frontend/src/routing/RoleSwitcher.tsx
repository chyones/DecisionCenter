import { useRole } from './RoleContext';
import { ROLES, type Role } from './roles';

/**
 * Dev-only role switcher.
 *
 * Per `docs/design/PHASE_1I_UI_CONTRACT.md` §D (dev-only helpers):
 * - Local/dev-only only.
 * - Not visible in production navigation.
 * - Not treated as a Phase 1I user-facing screen.
 * - Does not bypass RBAC guards.
 * - Excluded from production builds via `import.meta.env.DEV`.
 */
export function RoleSwitcher() {
  if (!import.meta.env.DEV) {
    return null;
  }

  const { role, setRole } = useRole();

  return (
    <div className="fixed bottom-4 right-4 z-[90] rounded-md border border-border bg-surface-overlay p-3 shadow-lg">
      <p className="mb-2 text-caption font-medium text-text-muted">
        Dev role switcher
      </p>
      <div className="flex max-w-[280px] flex-wrap gap-1">
        {ROLES.map((r: Role) => (
          <button
            key={r}
            type="button"
            onClick={() => setRole(r)}
            className={[
              'rounded-sm px-2 py-1 text-caption font-medium transition-colors',
              r === role
                ? 'bg-accent text-text-primary'
                : 'bg-surface-base text-text-secondary hover:bg-surface-raised',
            ].join(' ')}
          >
            {r}
          </button>
        ))}
      </div>
    </div>
  );
}
