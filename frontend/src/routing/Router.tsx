import { useRole } from './RoleContext';
import { useHashPath } from './useHashPath';
import { isRouteAllowed, getDefaultLanding } from './guards';
import { PlaceholderScreen } from '../screens/PlaceholderScreen';
import { ForbiddenScreen } from '../screens/ForbiddenScreen';
import { AdminHealthScreen } from '../screens/AdminHealthScreen';
import { AdminPermissionsScreen } from '../screens/AdminPermissionsScreen';
import { AdminSourceMappingScreen } from '../screens/AdminSourceMappingScreen';
import { AdminConnectorsScreen } from '../screens/AdminConnectorsScreen';
import { AdminAuditLogScreen } from '../screens/AdminAuditLogScreen';
import { QueryComposerScreen } from '../screens/QueryComposerScreen';
import { ReportsListScreen } from '../screens/ReportsListScreen';
import { ProcessingScreen } from '../screens/ProcessingScreen';
import { ReportViewScreen } from '../screens/ReportViewScreen';

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
    return <QueryComposerScreen />;
  }

  if (path === '/workspace/reports') {
    return <ReportsListScreen />;
  }

  if (path.startsWith('/workspace/report/') && path.endsWith('/processing')) {
    return <ProcessingScreen />;
  }

  if (path.startsWith('/workspace/report/')) {
    return <ReportViewScreen />;
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
    return <AdminHealthScreen />;
  }

  if (path === '/admin/permissions') {
    return <AdminPermissionsScreen />;
  }

  if (path === '/admin/source-mapping') {
    return <AdminSourceMappingScreen />;
  }

  if (path === '/admin/connectors') {
    return <AdminConnectorsScreen />;
  }

  if (path === '/admin/audit') {
    return <AdminAuditLogScreen />;
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
