import { AppShell } from './layout';
import { RoleProvider, Router, RoleSwitcher } from './routing';
import { ToastProvider } from './components';

function App() {
  return (
    <RoleProvider>
      <ToastProvider>
        <AppShell>
          <Router />
        </AppShell>
        <RoleSwitcher />
      </ToastProvider>
    </RoleProvider>
  );
}

export default App;
