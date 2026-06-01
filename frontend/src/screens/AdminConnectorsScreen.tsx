/**
 * Connectors & APIs (`/admin/connectors`) — admin-only.
 *
 * Honest connector status. Reads `GET /admin/connectors/truth` (the Connector
 * Status Truth model) and renders explicit states with evidence and "Last
 * verified" timestamps. Nothing is shown green unless a real live probe
 * returned `LIVE_OK`; missing credentials show `Not configured`, and configured
 * dependencies with no live proof show `Configured — not tested`.
 *
 * Backend: apps/edr/admin/connector_status.py. Credential values are never
 * rendered — only non-secret config key names and presence (C-6).
 */
import { ConnectorTruthPanel } from './ConnectorTruthPanel';

export function AdminConnectorsScreen() {
  return (
    <div>
      <div className="mb-6 flex items-baseline justify-between">
        <h1 className="text-display font-semibold text-text-primary">
          Connectors &amp; APIs
        </h1>
        <span className="text-caption text-text-muted">
          read-only · admin · live-probe truth
        </span>
      </div>
      <ConnectorTruthPanel variant="full" />
    </div>
  );
}
