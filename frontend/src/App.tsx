import { AppShell } from './layout';

function App() {
  return (
    <AppShell>
      <div className="rounded-md border border-border bg-surface-raised p-6">
        <h1 className="text-display font-semibold text-text-primary">
          DecisionCenter
        </h1>
        <p className="mt-2 text-body text-text-secondary">
          Phase 1I — Slice 4 layout shell. No routes, no screens, no API calls.
        </p>
        <p className="mt-4 text-caption text-text-muted">
          State: static_scaffold
        </p>
      </div>
    </AppShell>
  );
}

export default App;
