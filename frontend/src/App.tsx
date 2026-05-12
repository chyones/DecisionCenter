import { AppShell } from './layout';
import { RoleProvider, Router, RoleSwitcher } from './routing';

function App() {
  return (
    <RoleProvider>
      <AppShell>
        <Router />
      </AppShell>
      <RoleSwitcher />
    </RoleProvider>
  );
}

export default App;
