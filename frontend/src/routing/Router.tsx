import { useRole } from './RoleContext';
import { useHashPath } from './useHashPath';
import { isRouteAllowed, getDefaultLanding } from './guards';
import { PlaceholderScreen } from '../screens/PlaceholderScreen';
import { ForbiddenScreen } from '../screens/ForbiddenScreen';

export function Router() {
  const { role } = useRole();
  const path = useHashPath();

  // Redirect "/" to the role-appropriate default landing (contract §F.1).
  if (path === '/') {
    const landing = getDefaultLanding(role);
    window.location.replace('#' + landing);
    return null;
  }

  // Client-side guard: forbidden routes render the forbidden state.
  if (!isRouteAllowed(role, path)) {
    return <ForbiddenScreen />;
  }

  // Workspace routes
  if (path === '/workspace/new') {
    return (
      <PlaceholderScreen
        title="Query Composer"
        state="static_scaffold"
        body="Form shell with no project data and no submit behavior."
      />
    );
  }

  if (path === '/workspace/reports') {
    return (
      <PlaceholderScreen
        title="Reports"
        state="phase_2a_placeholder"
        body="This screen will list your reports and their status. It is not available in the current phase."
      />
    );
  }

  if (path.startsWith('/workspace/')) {
    return (
      <PlaceholderScreen
        title="Workspace"
        state="phase_2a_placeholder"
      />
    );
  }

  // Admin routes
  if (path === '/admin') {
    return (
      <PlaceholderScreen
        title="Admin Dashboard"
        state="phase_2b_placeholder"
        body="System overview, service status, and operational metrics will appear here."
      />
    );
  }

  if (path === '/admin/health') {
    return (
      <PlaceholderScreen
        title="System Health"
        state="static_scaffold"
        body="Static table shaped like the System Health screen. No live data."
      />
    );
  }

  if (path === '/admin/permissions') {
    return (
      <PlaceholderScreen
        title="Permissions & Roles"
        state="static_scaffold"
        body="Role Matrix tab only. Read-only from rbac_matrix.md."
      />
    );
  }

  if (path === '/admin/source-mapping') {
    return (
      <PlaceholderScreen
        title="Project Source Mapping"
        state="static_scaffold"
        body="Read-only view of the mapping shape. No credentials are shown."
      />
    );
  }

  if (path.startsWith('/admin/')) {
    return (
      <PlaceholderScreen
        title="Admin"
        state="phase_2b_placeholder"
      />
    );
  }

  // Unmatched paths fall through to forbidden.
  return <ForbiddenScreen />;
}
