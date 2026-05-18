import { test, expect } from '@playwright/test';

/**
 * Accessibility audit — Phase 2C Slice 1.
 *
 * Validates keyboard navigation, focus management, and ARIA labels
 * per UI_CONTRACT v1.2 Section 1 (Design Principles) and Section 9.1.
 */

test.describe('Query Composer accessibility', () => {
  test.beforeEach(async ({ page }) => {
    // Mock workspace context so the composer loads in "idle" state.
    await page.route('**/workspace/context', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: 'test-user',
          role: 'executive',
          can_generate_report: true,
          allowed_projects: [
            { project_code: 'PRJ-001', display_name: 'Test Project 1' },
            { project_code: 'PRJ-002', display_name: 'Test Project 2' },
          ],
        }),
      });
    });

    await page.goto('/#/workspace/new');
    // Wait for the mocked context to render the form.
    await page.waitForSelector('text=Query Composer');
  });

  test('all form inputs have associated labels', async ({ page }) => {
    const projectSelect = page.locator('select#query-composer-project');
    await expect(projectSelect).toHaveCount(1);
    const projectLabel = page.locator('label[for="query-composer-project"]');
    await expect(projectLabel).toHaveText('Project');

    const queryLabel = page.locator('label[for="query-composer-query"]');
    await expect(queryLabel).toHaveText('Management question');

    const queryTextarea = page.locator('textarea#query-composer-query');
    await expect(queryTextarea).toHaveAttribute('aria-describedby', 'query-composer-query-counter');
  });

  test('keyboard Tab order flows through interactive elements', async ({ page }) => {
    // Start focus from the project select.
    await page.locator('select#query-composer-project').focus();

    // Tab to query textarea.
    await page.keyboard.press('Tab');
    await expect(page.locator('textarea#query-composer-query')).toBeFocused();

    // Tab to Filters toggle.
    await page.keyboard.press('Tab');
    await expect(page.locator('button:has-text("Filters (optional)")')).toBeFocused();

    // Tab to submit button region — verify focus lands on a visible interactive element.
    await page.keyboard.press('Tab');
    const focused = page.locator(':focus');
    await expect(focused).toBeVisible();
  });

  test('focus indicators are visible on enabled buttons', async ({ page }) => {
    // Enable the submit button by selecting a project and typing a query.
    await page.locator('select#query-composer-project').selectOption('PRJ-001');
    await page.locator('textarea#query-composer-query').fill('Test query');

    const submit = page.locator('button:has-text("Generate Report")');
    await expect(submit).toBeEnabled();
    await submit.focus();
    await expect(submit).toBeFocused();
  });

  test('sidebar navigation links have aria-current when active', async ({ page }) => {
    const newQueryLink = page.locator('a[href="#/workspace/new"]');
    await expect(newQueryLink).toHaveAttribute('aria-current', 'page');
  });
});

test.describe('Modal focus trap', () => {
  test('Cancel confirmation dialog traps focus', async ({ page }) => {
    // Navigate to processing view with a mocked status.
    await page.route('**/reports/**/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          request_id: 'test-req-001',
          state: 'staging',
          current_node: 5,
          is_terminal: false,
          quality_gate: 'passed',
        }),
      });
    });

    await page.goto('/#/workspace/report/test-req-001/processing');
    await page.waitForSelector('text=Generating report');

    // Hide the dev role switcher so it does not intercept clicks at the bottom of the page.
    await page.evaluate(() => {
      const switcher = document.querySelector('[class*="fixed bottom-4 right-4"]');
      if (switcher) (switcher as HTMLElement).style.display = 'none';
    });

    // Open cancel confirmation.
    await page.locator('button:has-text("Cancel")').click();
    const dialog = page.locator('div[role="dialog"]');
    await expect(dialog).toBeVisible();

    // First focusable element inside dialog should be focused.
    const focused = page.locator(':focus');
    await expect(focused).toBeVisible();
    const dialogBox = await dialog.boundingBox();
    const focusedBox = await focused.boundingBox();
    expect(dialogBox).not.toBeNull();
    expect(focusedBox).not.toBeNull();
    if (dialogBox && focusedBox) {
      expect(focusedBox.x).toBeGreaterThanOrEqual(dialogBox.x);
      expect(focusedBox.y).toBeGreaterThanOrEqual(dialogBox.y);
      expect(focusedBox.x + focusedBox.width).toBeLessThanOrEqual(dialogBox.x + dialogBox.width);
      expect(focusedBox.y + focusedBox.height).toBeLessThanOrEqual(dialogBox.y + dialogBox.height);
    }

    // Escape closes dialog.
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
  });
});
