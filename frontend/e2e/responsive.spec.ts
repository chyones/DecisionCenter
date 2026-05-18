import { test, expect } from '@playwright/test';

/**
 * Responsive audit — Phase 2C Slice 1.
 *
 * Validates minimum 768px width behaviour, sidebar collapse, and detail panel
 * per UI_CONTRACT v1.2 Section 1.3 (Layout System).
 */

test.describe('Sidebar responsive behaviour', () => {
  test('sidebar collapses and expands via toggle button', async ({ page }) => {
    await page.goto('/#/workspace/new');

    const sidebar = page.locator('aside').first();
    await expect(sidebar).toBeVisible();

    // Verify sidebar starts expanded (width ~220px from CSS var).
    const expandedBox = await sidebar.boundingBox();
    expect(expandedBox).not.toBeNull();
    if (expandedBox) {
      expect(expandedBox.width).toBeGreaterThan(150);
    }

    // Click collapse toggle.
    const collapseButton = page.locator('button[aria-label="Collapse sidebar"]');
    await expect(collapseButton).toBeVisible();
    await collapseButton.click();
    await page.waitForTimeout(300); // Allow CSS transition.

    // After collapse, width should be much smaller (~48px rail).
    const collapsedBox = await sidebar.boundingBox();
    expect(collapsedBox).not.toBeNull();
    if (collapsedBox) {
      expect(collapsedBox.width).toBeLessThan(120);
    }

    // Click expand toggle.
    const expandButton = page.locator('button[aria-label="Expand sidebar"]');
    await expect(expandButton).toBeVisible();
    await expandButton.click();
    await page.waitForTimeout(300);

    // Sidebar should be expanded again.
    const reexpandedBox = await sidebar.boundingBox();
    expect(reexpandedBox).not.toBeNull();
    if (reexpandedBox) {
      expect(reexpandedBox.width).toBeGreaterThan(150);
    }
  });

  test('main content shifts when sidebar collapses', async ({ page }) => {
    await page.goto('/#/workspace/new');

    const main = page.locator('main');
    const mainBeforeBox = await main.boundingBox();
    expect(mainBeforeBox).not.toBeNull();

    // Collapse sidebar.
    await page.locator('button[aria-label="Collapse sidebar"]').click();
    await page.waitForTimeout(300); // Allow CSS transition.

    const mainAfterBox = await main.boundingBox();
    expect(mainAfterBox).not.toBeNull();

    if (mainBeforeBox && mainAfterBox) {
      // Main content left edge should move left when sidebar collapses.
      expect(mainAfterBox.x).toBeLessThan(mainBeforeBox.x);
    }
  });
});

test.describe('Viewport width enforcement', () => {
  test('unsupported width overlay appears below 768px', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/#/workspace/new');

    const overlay = page.locator('text=Minimum viewport width is 768px');
    await expect(overlay).toBeVisible();
  });

  test('unsupported width overlay is hidden at 768px and above', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/#/workspace/new');

    const overlay = page.locator('text=Minimum viewport width is 768px');
    await expect(overlay).not.toBeVisible();
  });
});

test.describe('Detail panel behaviour', () => {
  test('evidence panel slides in and can be closed', async ({ page }) => {
    // Mock a report with evidence so the Evidence button appears.
    await page.route('**/reports/test-evidence/content', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          request_id: 'test-evidence',
          project_code: 'PRJ-001',
          state: 'approved',
          quality_gate: 'passed',
          quality_gate_flags: [],
          content_available: true,
          markdown: '# Decision Report\nClaim [ev_001].',
          evidence: [
            {
              evidence_id: 'ev_001',
              citation_label: '1',
              title: 'Test Evidence',
              source_type: 'SharePoint',
              confidence: 'High',
              hash_short: 'a1b2c3d4',
              excerpt: 'This is a test excerpt.',
            },
          ],
          can_review: false,
          immutable: true,
        }),
      });
    });

    await page.goto('/#/workspace/report/test-evidence');
    await page.waitForSelector('text=Decision Report');

    // Open evidence panel.
    await page.locator('button:has-text("Evidence")').click();
    const panel = page.locator('aside[aria-label="Detail panel"]').filter({ hasText: 'Evidence' });
    await expect(panel).toBeVisible();

    // Close via close button.
    await page.locator('aside[aria-label="Detail panel"] button[aria-label="Close panel"]').click();
    await expect(panel).not.toBeVisible();
  });
});
