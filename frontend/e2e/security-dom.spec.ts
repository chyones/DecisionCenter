import { test, expect } from '@playwright/test';

/**
 * Security-DOM audit — Phase 2C Slice 1.
 *
 * Validates:
 * - Admin owner-operator role can access workspace report content and Query Composer.
 * - quality_gate = "failed" removes Export Panel from DOM entirely (UI_CONTRACT §8.4, U-06).
 * - No credential values appear in admin connector screens (UI_CONTRACT §8.3, C-6).
 */

async function setRole(page: import('@playwright/test').Page, role: string) {
  await page.goto('/#/workspace/new');
  const roleSwitcher = page.locator('text=Dev role switcher');
  await expect(roleSwitcher).toBeVisible();
  await page.locator(`button:has-text("${role}")`).click();
}

test.describe('Admin owner-operator workspace access', () => {
  test('admin navigating to workspace report sees report content', async ({ page }) => {
    await page.route('**/reports/test-id-123/content', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          request_id: 'test-id-123',
          project_code: 'PRJ-001',
          state: 'approved',
          quality_gate: 'passed',
          quality_gate_flags: [],
          content_available: true,
          content_unavailable_reason: null,
          markdown: '# Owner Report\n\n## 1. Executive Summary\n\nAdmin owner-operator content.',
          evidence: [],
          can_review: true,
          immutable: false,
        }),
      });
    });

    await setRole(page, 'admin');
    await page.goto('/#/workspace/report/test-id-123');
    await page.waitForSelector('text=Owner Report');

    await expect(page.locator('h2:has-text("Access denied")')).toHaveCount(0);
    await expect(page.locator('article')).toHaveCount(1);
    await expect(page.locator('text=Admin owner-operator content.')).toBeVisible();
    await expect(page.locator('div[role="alert"]:has-text("Quality gate failed")')).toHaveCount(0);
  });

  test('admin can use query composer', async ({ page }) => {
    await page.route('**/workspace/context', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: 'admin-owner',
          role: 'admin',
          can_generate_report: true,
          allowed_projects: [{ project_code: 'PRJ-001', name: 'Project 001' }],
        }),
      });
    });

    await setRole(page, 'admin');
    await page.goto('/#/workspace/new');
    await page.waitForSelector('text=Query Composer');

    await expect(page.locator('h2:has-text("Access denied")')).toHaveCount(0);
    await expect(page.locator('label:has-text("Management question")')).toBeVisible();
    await expect(page.locator('button:has-text("Generate Report")')).toBeVisible();
  });
});

test.describe('Quality gate failed removes Export Panel', () => {
  test.beforeEach(async ({ page }) => {
    // Mock report content with failed quality gate.
    await page.route('**/reports/test-qg-failed/content', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          request_id: 'test-qg-failed',
          project_code: 'PRJ-001',
          state: 'staging',
          quality_gate: 'failed',
          quality_gate_flags: ['Insufficient evidence', 'Missing Odoo financial data'],
          content_available: false,
          content_unavailable_reason: 'Report content and exports are blocked because the quality gate failed.',
          markdown: '',
          evidence: [],
          can_review: false,
          immutable: false,
        }),
      });
    });
  });

  test('no Export button or ExportPanel in DOM when QG failed', async ({ page }) => {
    await page.goto('/#/workspace/report/test-qg-failed');
    await page.waitForSelector('text=Quality gate failed');

    // Export button must not exist.
    await expect(page.locator('button:has-text("Export")')).toHaveCount(0);

    // ExportPanel is a SlideInPanel with aria-label "Detail panel".
    // It should not be mounted at all.
    await expect(page.locator('aside[aria-label="Detail panel"]').filter({ hasText: 'Export' })).toHaveCount(0);

    // Error banner must be present.
    await expect(page.locator('div[role="alert"]:has-text("Quality gate failed")')).toBeVisible();
  });
});

test.describe('Credential handling (C-6)', () => {
  test('admin connectors screen shows presence indicators only', async ({ page }) => {
    // Mock services endpoint to return connector metadata.
    await page.route('**/admin/services', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { name: 'sharepoint', display_name: 'SharePoint', last_probe_status: 'pass' as const },
          { name: 'odoo', display_name: 'Odoo ERP', last_probe_status: 'pass' as const },
        ]),
      });
    });

    await page.route('**/admin/services/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          name: 'sharepoint',
          display_name: 'SharePoint',
          category: 'search',
          auth_mechanism: 'OAuth2',
          hostname: 'graph.microsoft.com',
          last_probe_status: 'pass',
          last_probe_at: new Date().toISOString(),
          last_latency_ms: 120,
          description: 'Microsoft Graph search integration.',
          env_keys: [
            { name: 'SHAREPOINT_SEARCH_WEBHOOK', present: true },
            { name: 'SHAREPOINT_CLIENT_SECRET', present: true },
          ],
          recent_events: [],
        }),
      });
    });

    await setRole(page, 'admin');
    await page.goto('/#/admin/connectors');
    await page.waitForSelector('text=Connectors');

    // No credential values should appear in the DOM.
    const bodyText = await page.locator('body').innerText();
    expect(bodyText).not.toContain('sk-');
    expect(bodyText).not.toContain('secret');
    expect(bodyText).not.toContain('password');
    // Specific connector credentials must not be present.
    expect(bodyText).not.toContain('http://localhost:8069');
  });
});
