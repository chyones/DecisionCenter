/**
 * React hook — binds auth to the API client.
 *
 * Production (`productionAuthEnabled`): attaches `Authorization: Bearer <token>`
 * acquired from MSAL. Dev/CI: sends the `X-User-Role` bypass header matching the
 * current RoleContext role. Phase 2D Slice 2.
 */

import { useMemo } from 'react';

import { useRole } from '../routing';
import { acquireAccessToken, productionAuthEnabled } from '../auth/msalConfig';
import { ApiClient } from './client';

export function useApi(): ApiClient {
  const { role } = useRole();
  const userId = `phase2a-${role}@local.test`;

  return useMemo(
    () =>
      new ApiClient({
        getAuthHeaders: productionAuthEnabled
          ? async () => {
              const token = await acquireAccessToken();
              return { authorization: `Bearer ${token}` };
            }
          : () => ({
              'x-user-role': role,
              'x-user-id': userId,
            }),
      }),
    [role, userId],
  );
}
