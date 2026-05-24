import { test, expect } from '@playwright/test';

/**
 * Performance audit — Phase 2C Slice 2.
 *
 * Validates render timing for Processing View and Report View
 * against internal budgets. Uses browser Performance APIs via
 * page.evaluate() — no external tooling required.
 */

const BUDGETS = {
  // Time from navigation to first visible heading/text
  processingFcpMs: 1500,
  reportFcpMs: 2000,
  // Time for main content skeleton to be ready
  processingContentReadyMs: 2000,
  reportContentReadyMs: 2000,
};

test.describe('Processing View performance', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/reports/**/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          request_id: 'perf-req-001',
          state: 'running',
          current_node: 5,
          is_terminal: false,
          quality_gate: 'passed',
        }),
      });
    });
  });

  test('renders heading and progress bar within budget', async ({ page }) => {
    const start = Date.now();
    await page.goto('/#/workspace/report/perf-req-001/processing');

    const heading = page.locator('h1:has-text("Generating report")');
    await heading.waitFor({ state: 'visible', timeout: BUDGETS.processingFcpMs });
    const headingElapsed = Date.now() - start;

    const progressBar = page.locator('div[class*="h-2 w-full rounded-sm"]');
    await progressBar.waitFor({ state: 'visible', timeout: BUDGETS.processingContentReadyMs });
    const contentElapsed = Date.now() - start;

    // Also assert via Performance Timing API where available.
    const perf = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      return nav
        ? {
            domContentLoaded: nav.domContentLoadedEventEnd - nav.startTime,
            loadComplete: nav.loadEventEnd - nav.startTime,
          }
        : null;
    });

    console.log(`Processing View: heading ${headingElapsed}ms, content ${contentElapsed}ms`, perf);

    expect(headingElapsed).toBeLessThan(BUDGETS.processingFcpMs);
    expect(contentElapsed).toBeLessThan(BUDGETS.processingContentReadyMs);
    if (perf) {
      expect(perf.domContentLoaded).toBeLessThan(3000);
      expect(perf.loadComplete).toBeLessThan(5000);
    }
  });
});

test.describe('Report View performance', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/workspace/context', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: 'test-user',
          role: 'executive',
          can_generate_report: true,
          allowed_projects: [{ project_code: 'PRJ-001', display_name: 'Test Project 1' }],
        }),
      });
    });

    await page.route('**/reports/perf-report-001/content', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          request_id: 'perf-report-001',
          project_code: 'PRJ-001',
          state: 'final',
          quality_gate: 'passed',
          quality_gate_flags: [],
          content_available: true,
          content_unavailable_reason: '',
          markdown: '# Executive Summary\n\nTest report content for performance measurement.\n\n## Financial Snapshot\n\n- Revenue: 1.2M AED\n\n## Sources\n\n[EVIDENCE-001]',
          evidence: [
            {
              evidence_id: 'EVIDENCE-001',
              citation_label: '¹',
              source_type: 'odoo',
              source_label: 'Odoo ERP',
              confidence_score: 0.95,
              confidence_label: 'High',
              excerpt: 'Sample evidence excerpt',
            },
          ],
          can_review: false,
          immutable: true,
        }),
      });
    });
  });

  test('renders report header and article within budget', async ({ page }) => {
    const start = Date.now();
    await page.goto('/#/workspace/report/perf-report-001');

    const header = page.locator('h1:has-text("Executive Summary")');
    await header.waitFor({ state: 'visible', timeout: BUDGETS.reportFcpMs });
    const headerElapsed = Date.now() - start;

    const article = page.locator('article');
    await article.waitFor({ state: 'visible', timeout: BUDGETS.reportContentReadyMs });
    const contentElapsed = Date.now() - start;

    const perf = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      return nav
        ? {
            domContentLoaded: nav.domContentLoadedEventEnd - nav.startTime,
            loadComplete: nav.loadEventEnd - nav.startTime,
          }
        : null;
    });

    console.log(`Report View: header ${headerElapsed}ms, content ${contentElapsed}ms`, perf);

    expect(headerElapsed).toBeLessThan(BUDGETS.reportFcpMs);
    expect(contentElapsed).toBeLessThan(BUDGETS.reportContentReadyMs);
    if (perf) {
      expect(perf.domContentLoaded).toBeLessThan(3000);
      expect(perf.loadComplete).toBeLessThan(5000);
    }
  });

  test('evidence panel opens without layout shift', async ({ page }) => {
    await page.goto('/#/workspace/report/perf-report-001');
    await page.waitForSelector('article');

    const articleBoxBefore = await page.locator('article').boundingBox();
    expect(articleBoxBefore).not.toBeNull();

    await page.locator('button:has-text("Evidence")').click();
    await page.waitForSelector('aside[aria-label="Detail panel"]');

    const articleBoxAfter = await page.locator('article').boundingBox();
    expect(articleBoxAfter).not.toBeNull();

    // Article should not shift vertically when panel opens (slide-in from right).
    if (articleBoxBefore && articleBoxAfter) {
      expect(Math.abs(articleBoxAfter.y - articleBoxBefore.y)).toBeLessThan(5);
      expect(Math.abs(articleBoxAfter.x - articleBoxBefore.x)).toBeLessThan(5);
    }
  });
});
