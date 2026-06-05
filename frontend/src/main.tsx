import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App';
import { initAuth } from './auth/msalConfig';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root not found');
}

async function bootstrap() {
  try {
    await initAuth();
  } catch {
    // MSAL redirect error (e.g. AADSTS50011 from unregistered redirect URI) —
    // still render so the user sees the login screen rather than a blank page.
  }
  createRoot(rootElement!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void bootstrap();
