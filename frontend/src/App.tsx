import { MsalProvider } from '@azure/msal-react';

import { AppShell } from './layout';
import { RoleProvider, Router, RoleSwitcher } from './routing';
import { ToastProvider } from './components';
import { LoginGate } from './auth/LoginGate';
import { pca, productionAuthEnabled } from './auth/msalConfig';

function App() {
  if (productionAuthEnabled && pca) {
    return (
      <MsalProvider instance={pca}>
        <RoleProvider>
          <ToastProvider>
            <LoginGate>
              <AppShell>
                <Router />
              </AppShell>
            </LoginGate>
          </ToastProvider>
        </RoleProvider>
      </MsalProvider>
    );
  }

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
