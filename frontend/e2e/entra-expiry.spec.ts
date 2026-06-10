import { expect, test, type Page, type Route } from '@playwright/test';

const LAST_SUCCESS = '2026-06-10T06:00:00Z';
const EXPIRED_AT = '2026-06-10T07:00:00Z';
const LAST_CHECKED = '2026-06-10T07:30:00Z';
const CURRENT_EXPIRY = '2026-06-10T09:00:00Z';

type EntraState =
  | 'AUTH_FAILED'
  | 'CONFIGURED_NOT_TESTED'
  | 'PREVIOUSLY_VALIDATED_TOKEN_EXPIRED'
  | 'VALIDATED';

async function setAdminRole(page: Page) {
  await page.goto('/#/workspace/new');
  await expect(page.getByText('Dev role switcher')).toBeVisible();
  await page.getByRole('button', { name: 'admin', exact: true }).click();
}

function entraTruth(
  state: EntraState,
  evidence = 'OIDC discovery and JWKS reachable; no fresh user-token validation evidence',
) {
  const validated = state === 'VALIDATED';
  const expired = state === 'PREVIOUSLY_VALIDATED_TOKEN_EXPIRED';
  const failed = state === 'AUTH_FAILED';
  return {
    name: 'entra_auth',
    display_name: 'Microsoft Entra authentication',
    group: 'auth',
    state,
    summary: `Microsoft Entra authentication: ${state}`,
    configured: true,
    missing_required_config: [],
    secret_present: true,
    auth_ok: validated ? true : failed ? false : null,
    network_ok: true,
    permission_ok: validated ? true : null,
    live_data_ok: validated ? true : expired ? false : null,
    data_source: validated || expired ? 'evidence' : 'none',
    last_probe_at: LAST_CHECKED,
    last_success_at: validated || expired ? LAST_SUCCESS : null,
    token_expires_at: validated ? CURRENT_EXPIRY : expired ? EXPIRED_AT : null,
    last_error_safe: failed ? 'Microsoft session validation failed' : null,
    sample_count: validated ? 1 : null,
    evidence: validated
      ? 'Fresh Entra authentication validation accepted.'
      : expired
        ? 'Previous Entra validation expired and requires revalidation.'
        : evidence,
    required_for_go_live: true,
    blocks_go_live: !validated,
  };
}

function report(state: EntraState, evidence?: string) {
  return {
    readiness: 'PARTIAL_READY',
    readiness_reason: 'Microsoft login requires attention.',
    report_generation: 'BLOCKED',
    report_generation_reason: 'Provider keys missing.',
    generated_at: LAST_CHECKED,
    core_platform: [],
    auth: [entraTruth(state, evidence)],
    external_connectors: [],
    ai_providers: [],
    edge: [],
    blocking: state === 'VALIDATED' ? [] : ['entra_auth'],
  };
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function mockMsalAcquisitionFailure(page: Page) {
  await page.route('**/src/auth/msalConfig.ts', async (route) => {
    const response = await route.fetch();
    let body = await response.text();
    const original = body;
    body = body.replace(
      'export const productionAuthEnabled = import.meta.env.PROD && pca !== null;',
      'export const productionAuthEnabled = true;',
    );
    body = body.replace(
      /export async function acquireAccessToken\(options = \{\}\) \{[\s\S]*?\n\}\nexport async function signOut/,
      `export async function acquireAccessToken(options = {}) {
  window.__decisionCenterMsalAcquireOptions = options;
  return "";
}
export async function signOut`,
    );
    expect(body).not.toBe(original);
    await route.fulfill({
      response,
      body,
      headers: {
        ...response.headers(),
        'content-type': 'application/javascript',
      },
    });
  });
}

test.describe('Entra browser-session validation card', () => {
  test('button appears for configured_not_tested', async ({ page }) => {
    await page.route('**/admin/connectors/truth**', (route) =>
      fulfillJson(route, report('CONFIGURED_NOT_TESTED')),
    );

    await setAdminRole(page);
    await page.goto('/#/admin/connectors');

    await expect(page.getByText('Configured — not tested', { exact: true })).toBeVisible();
    await expect(
      page.getByRole('button', {
        name: 'Validate with current Microsoft session',
      }),
    ).toBeVisible();
  });

  test('button appears when no fresh user-token evidence exists', async ({
    page,
  }) => {
    await page.route('**/admin/connectors/truth**', (route) =>
      fulfillJson(route, report('CONFIGURED_NOT_TESTED', '')),
    );

    await setAdminRole(page);
    await page.goto('/#/admin/connectors');

    await expect(page.getByText('Evidence')).toBeVisible();
    await expect(
      page.getByRole('button', {
        name: 'Validate with current Microsoft session',
      }),
    ).toBeVisible();
  });

  test('expired validation remains action-required with revalidation visible', async ({
    page,
  }) => {
    await page.route('**/admin/connectors/truth**', (route) =>
      fulfillJson(route, report('PREVIOUSLY_VALIDATED_TOKEN_EXPIRED')),
    );

    await setAdminRole(page);
    await page.goto('/#/admin/connectors');

    await expect(page.getByText('Expired', { exact: true })).toBeVisible();
    await expect(page.getByText('Last successful validation')).toBeVisible();
    await expect(page.getByText('Token expired at')).toBeVisible();
    await expect(page.getByText('Last checked')).toBeVisible();
    await expect(
      page.getByRole('button', {
        name: 'Revalidate with current Microsoft session',
      }),
    ).toBeVisible();
  });

  test('action-required failure state keeps the validation button visible', async ({
    page,
  }) => {
    await page.route('**/admin/connectors/truth**', (route) =>
      fulfillJson(route, report('AUTH_FAILED')),
    );

    await setAdminRole(page);
    await page.goto('/#/admin/connectors');

    await expect(page.getByText('Auth failed', { exact: true })).toBeVisible();
    await expect(
      page.getByRole('button', {
        name: 'Validate with current Microsoft session',
      }),
    ).toBeVisible();
  });

  test('successful validation updates the card to validated and current', async ({
    page,
  }) => {
    let state: EntraState = 'CONFIGURED_NOT_TESTED';
    await page.route(
      '**/admin/connectors/entra/revalidate-current-token',
      async (route) => {
        expect(route.request().method()).toBe('POST');
        state = 'VALIDATED';
        await fulfillJson(route, {
          result: 'PASS',
          validated_at: LAST_CHECKED,
          token_expires_at: CURRENT_EXPIRY,
          role: 'admin',
          checks: { user_identity_ok: true },
        });
      },
    );
    await page.route('**/admin/connectors/truth**', (route) =>
      fulfillJson(route, report(state)),
    );

    await setAdminRole(page);
    await page.goto('/#/admin/connectors');
    await page
      .getByRole('button', {
        name: 'Validate with current Microsoft session',
      })
      .click();

    await expect(page.getByText('Validated', { exact: true })).toBeVisible();
    await expect(page.getByText('Current validation evidence')).toBeVisible();
    await expect(page.getByText('Token expires at')).toBeVisible();
    await expect(
      page.getByRole('button', {
        name: 'Revalidate with current Microsoft session',
      }),
    ).toBeVisible();
    await expect(page.getByText('Configured — not tested')).toHaveCount(0);
    await expect(
      page.getByText('no fresh user-token validation evidence'),
    ).toHaveCount(0);
  });

  test('backend validation failure keeps the button and shows only a safe reason', async ({
    page,
  }) => {
    await page.route(
      '**/admin/connectors/entra/revalidate-current-token',
      (route) =>
        fulfillJson(
          route,
          { detail: 'Microsoft user identity validation failed' },
          400,
        ),
    );
    await page.route('**/admin/connectors/truth**', (route) =>
      fulfillJson(route, report('CONFIGURED_NOT_TESTED')),
    );

    await setAdminRole(page);
    await page.goto('/#/admin/connectors');
    await page
      .getByRole('button', {
        name: 'Validate with current Microsoft session',
      })
      .click();

    await expect(
      page.getByText('Microsoft user identity validation failed'),
    ).toBeVisible();
    await expect(
      page.getByRole('button', {
        name: 'Validate with current Microsoft session',
      }),
    ).toBeVisible();
    await expect(page.getByText('Configured — not tested', { exact: true })).toBeVisible();
  });

  test('MSAL acquisition failure keeps the button and asks the user to sign in', async ({
    page,
  }) => {
    let backendCalls = 0;
    await mockMsalAcquisitionFailure(page);
    await page.route(
      '**/admin/connectors/entra/revalidate-current-token',
      (route) => {
        backendCalls += 1;
        return fulfillJson(route, {}, 500);
      },
    );
    await page.route('**/admin/connectors/truth**', (route) =>
      fulfillJson(route, report('CONFIGURED_NOT_TESTED')),
    );

    await setAdminRole(page);
    await page.goto('/#/admin/connectors');
    const button = page.getByRole('button', {
      name: 'Validate with current Microsoft session',
    });
    await button.click();

    await expect(
      page.getByText('Sign in with Microsoft again, then retry validation'),
    ).toBeVisible();
    await expect(button).toBeVisible();
    expect(backendCalls).toBe(0);
    const options = await page.evaluate(
      () =>
        (
          window as Window & {
            __decisionCenterMsalAcquireOptions?: Record<string, boolean>;
          }
        ).__decisionCenterMsalAcquireOptions,
    );
    expect(options).toEqual({
      forceRefresh: true,
      interactiveFallback: false,
    });
  });

  test('card never renders raw credentials or internal endpoint instructions', async ({
    page,
  }) => {
    await page.route('**/admin/connectors/truth**', (route) =>
      fulfillJson(route, report('CONFIGURED_NOT_TESTED')),
    );

    await setAdminRole(page);
    await page.goto('/#/admin/connectors');

    const body = await page.locator('body').innerText();
    expect(body).not.toContain('Authorization: Bearer');
    expect(body).not.toContain('revalidate-current-token');
    expect(body).not.toContain('/admin/connectors');
    expect(body).not.toContain('Use POST');
    expect(body).not.toContain('secret-browser-value');
  });
});
