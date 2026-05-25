/**
 * MSAL (Microsoft Entra) configuration — Phase 2D Slice 2.
 *
 * Production auth is enabled only in production builds that also carry an Entra
 * client id. The Vite dev server (used by `npm run dev` and the Playwright e2e
 * suite) keeps the RoleSwitcher + `X-User-Role` bypass, so dev/CI is unaffected.
 */
import { PublicClientApplication, type Configuration } from '@azure/msal-browser';

const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID;
const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID;
const apiScope = import.meta.env.VITE_ENTRA_API_SCOPE;

const msalConfig: Configuration = {
  auth: {
    clientId: clientId ?? '',
    authority: `https://login.microsoftonline.com/${tenantId ?? 'common'}`,
    redirectUri: typeof window !== 'undefined' ? window.location.origin : '/',
  },
  cache: { cacheLocation: 'sessionStorage' },
};

/** MSAL client — only constructed when an Entra client id is configured. */
export const pca: PublicClientApplication | null = clientId
  ? new PublicClientApplication(msalConfig)
  : null;

/** True only in a production build that has a configured Entra client id. */
export const productionAuthEnabled: boolean = import.meta.env.PROD && pca !== null;

/** Scope whose access token has audience == ENTRA_CLIENT_ID (backend checks this). */
export const tokenScopes: string[] = apiScope
  ? [apiScope]
  : clientId
    ? [`api://${clientId}/.default`]
    : [];

/** Initialise MSAL and resolve any pending redirect. Call once before render. */
export async function initAuth(): Promise<void> {
  if (!pca) return;
  await pca.initialize();
  const result = await pca.handleRedirectPromise();
  if (result?.account) {
    pca.setActiveAccount(result.account);
  } else {
    const existing = pca.getAllAccounts();
    if (existing.length > 0) {
      pca.setActiveAccount(existing[0]);
    }
  }
}

/** Acquire an access token for API calls; redirects to login when needed. */
export async function acquireAccessToken(): Promise<string> {
  if (!pca) return '';
  const account = pca.getActiveAccount() ?? pca.getAllAccounts()[0];
  if (!account) {
    await pca.loginRedirect({ scopes: tokenScopes });
    return '';
  }
  try {
    const res = await pca.acquireTokenSilent({ account, scopes: tokenScopes });
    return res.accessToken;
  } catch {
    await pca.acquireTokenRedirect({ account, scopes: tokenScopes });
    return '';
  }
}

/** Sign the user out (production only). */
export async function signOut(): Promise<void> {
  if (!pca) return;
  await pca.logoutRedirect();
}
