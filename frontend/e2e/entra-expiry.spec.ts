import { expect, test, type Page, type Route } from '@playwright/test';

const LAST_SUCCESS = '2026-06-09T06:00:00Z';
const EXPIRED_AT = '2026-06-09T07:00:00Z';
const LAST_CHECKED = '2026-06-09T07:30:00Z';
const CURRENT_EXPIRY = '2026-06-09T09:00:00Z';

async function setAdminRole(page: Page) {
  await page.goto('/#/workspace/new');
  await expect(page.getByText('Dev role switcher')).toBeVisible();
  await page.getByRole('button', { name: 'admin', exact: true }).click();
}

function entraTruth(validated: boolean) {
  return {
    name: 'entra_auth',
    display_name: 'Microsoft Entra authentication',
    group: 'auth',
    state: validated ? 'VALIDATED' : 'PREVIOUSLY_VALIDATED_TOKEN_EXPIRED',
    summary: validated
      ? 'Microsoft Entra authentication: Validated'
      : 'Microsoft Entra authentication: Expired',
    configured: true,
    missing_required_config: [],
    secret_present: true,
    auth_ok: validated ? true : null,
    network_ok: true,
    permission_ok: validated ? true : null,
    live_data_ok: validated,
    data_source: 'evidence',
    last_probe_at: LAST_CHECKED,
    last_success_at: LAST_SUCCESS,
    token_expires_at: validated ? CURRENT_EXPIRY : EXPIRED_AT,
    last_error_safe: null,
    sample_count: validated ? 1 : null,
    evidence: validated
      ? 'Fresh Entra authentication validation accepted.'
      : 'Previous Entra validation expired and requires revalidation.',
    required_for_go_live: true,
    blocks_go_live: !validated,
  };
}

function report(validated: boolean) {
  return {
    readiness: 'PARTIAL_READY',
    readiness_reason: 'Microsoft login requires attention.',
    report_generation: 'BLOCKED',
    report_generation_reason: 'Provider keys missing.',
    generated_at: LAST_CHECKED,
    core_platform: [],
    auth: [entraTruth(validated)],
    external_connectors: [],
    ai_providers: [],
    edge: [],
    blocking: validated ? [] : ['entra_auth'],
  };
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

test.describe('Entra expired validation card', () => {
  test('renders expired history as action-required, not current validation', async ({
    page,
  }) => {
    await page.route('**/admin/connectors/truth**', (route) =>
      fulfillJson(route, report(false)),
    );

    await setAdminRole(page);
    await page.goto('/#/admin/connectors');

    await expect(page.getByText('Microsoft Entra authentication')).toBeVisible();
    await expect(page.getByText('Expired', { exact: true })).toBeVisible();
    await expect(page.getByText('Last successful validation')).toBeVisible();
    await expect(page.getByText('Token expired at')).toBeVisible();
    await expect(page.getByText('Last checked')).toBeVisible();
    await expect(
      page.getByRole('button', {
        name: 'Revalidate with current browser session',
      }),
    ).toBeVisible();

    const body = await page.locator('body').innerText();
    expect(body).not.toContain('validated once');
    expect(body).not.toContain('Current validation evidence');
    expect(body).not.toContain('Last verified');
    expect(body).not.toContain('Use POST');
    expect(body).not.toContain('current-token');
  });

  test('successful revalidation replaces expired UI with current validation', async ({
    page,
  }) => {
    let validated = false;
    await page.route(
      '**/admin/connectors/entra/revalidate-current-token',
      async (route) => {
        expect(route.request().method()).toBe('POST');
        validated = true;
        await fulfillJson(route, {
          result: 'PASS',
          validated_at: LAST_CHECKED,
          token_expires_at: CURRENT_EXPIRY,
          role: 'admin',
          checks: { me_role_ok: true },
        });
      },
    );
    await page.route('**/admin/connectors/truth**', (route) =>
      fulfillJson(route, report(validated)),
    );

    await setAdminRole(page);
    await page.goto('/#/admin/connectors');
    await page
      .getByRole('button', {
        name: 'Revalidate with current browser session',
      })
      .click();

    await expect(page.getByText('Validated', { exact: true })).toBeVisible();
    await expect(page.getByText('Current validation evidence')).toBeVisible();
    await expect(page.getByText('Token expires at')).toBeVisible();
    await expect(
      page.getByRole('button', {
        name: 'Revalidate with current browser session',
      }),
    ).toHaveCount(0);
    await expect(page.getByText('Revalidation complete')).toBeVisible();
  });

  test('failed revalidation keeps expired state and shows login guidance', async ({
    page,
  }) => {
    await page.route(
      '**/admin/connectors/entra/revalidate-current-token',
      (route) =>
        fulfillJson(
          route,
          { detail: 'Microsoft session validation failed.' },
          400,
        ),
    );
    await page.route('**/admin/connectors/truth**', (route) =>
      fulfillJson(route, report(false)),
    );

    await setAdminRole(page);
    await page.goto('/#/admin/connectors');
    await page
      .getByRole('button', {
        name: 'Revalidate with current browser session',
      })
      .click();

    await expect(page.getByText('Expired', { exact: true })).toBeVisible();
    await expect(
      page.getByText(
        'Your Microsoft session could not be validated. Sign in again, then retry.',
      ),
    ).toBeVisible();
  });
});
