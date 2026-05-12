/**
 * React hook — binds `RoleContext` to the API client for dev bypass auth.
 *
 * Phase 2A Slice 1: dev mode sends `X-User-Role` header matching the current
 * static role. Production will switch to Bearer token once Entra SSO is wired.
 */

import { useMemo } from 'react';

import { useRole } from '../routing';
import { ApiClient } from './client';

export function useApi(): ApiClient {
  const { role } = useRole();

  return useMemo(
    () =>
      new ApiClient({
        getAuthHeaders: () => ({
          // Dev bypass mode: backend accepts X-User-Role when Entra is not configured.
          'x-user-role': role,
        }),
      }),
    [role],
  );
}
