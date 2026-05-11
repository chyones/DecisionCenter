// Phase 1I bootstrap placeholder. Foundation slice only: no router, no design
// tokens, no reusable components, no API client, no auth. Subsequent Phase 1I
// slices add the design system, layout shell, components, and role-guarded
// routing per docs/design/PHASE_1I_UI_CONTRACT.md.
function App() {
  return (
    <main className="p-6">
      <h1 className="text-lg font-semibold">
        DecisionCenter — Phase 1I frontend bootstrap
      </h1>
      <p className="mt-2 text-sm">
        Toolchain only (Vite + React + TypeScript + Tailwind). No application
        code yet. See docs/design/PHASE_1I_UI_CONTRACT.md and
        docs/execution/PHASE_1I_PLAN.md.
      </p>
    </main>
  );
}

export default App;
