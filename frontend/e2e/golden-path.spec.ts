import { test, expect } from '@playwright/test';

/**
 * Golden-path acceptance test — Phase 2C Slice 3.
 *
 * Exercises the full user-visible report lifecycle:
 *   Query Composer → Processing View → Report View → Approve → Download
 *
 * All backend calls are mocked via page.route() — no real backend required.
 * Per UI_CONTRACT v1.2 §2.1–§2.4 and docs/execution/PHASE_2C_PLAN.md Slice 3.
 */

const REQUEST_ID = 'gp-req-001';

const WORKSPACE_CONTEXT = {
  user_id: 'gp-user-001',
  role: 'executive',
  allowed_projects: [
    { project_code: 'PRJ-GP-001', contract_numbers: ['CON-GP-001'] },
  ],
  can_generate_report: true,
  can_approve: true,
  can_access_odoo_budget: true,
};

const EVIDENCE = [
  {
    evidence_id: 'gp-ev-001',
    citation_label: '1',
    source_type: 'SharePoint',
    title: 'Contract Summary PRJ-GP-001',
    confidence: 'High',
    hash_sha256: 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
    hash_short: 'a1b2c3d4',
    excerpt: 'Total contract value: 5.2M AED. Milestone 3 complete.',
    source_uri: 'https://sharepoint.example.com/Contracts/PRJ-GP-001.pdf',
    timestamp: '2026-01-15T08:00:00Z',
  },
];

const REPORT_MARKDOWN = [
  '# Executive Decision Report',
  '',
  '## 1. Summary',
  '',
  'Based on available evidence the project is tracking within budget. [gp-ev-001]',
  '',
  '## 3. Recommendations',
  '',
  '- Continue current procurement plan.',
].join('\n');

function makeContent(state: string, canReview: boolean) {
  return {
    request_id: REQUEST_ID,
    project_code: 'PRJ-GP-001',
    query: 'What is the current financial position for PRJ-GP-001?',
    state,
    quality_gate: 'passed',
    requires_approval: true,
    markdown: REPORT_MARKDOWN,
    evidence: EVIDENCE,
    quality_gate_flags: [],
    content_available: true,
    content_unavailable_reason: null,
    can_review: canReview,
    is_requester: false,
    immutable: false,
  };
}

/** Hide the dev role switcher (fixed bottom-right) so it cannot intercept clicks. */
async function hideSwitcher(page: import('@playwright/test').Page) {
  await page.evaluate(() => {
    const el = document.querySelector('[class*="fixed bottom-4 right-4"]');
    if (el) (el as HTMLElement).style.display = 'none';
  });
}

test.describe('Golden path: submit → processing → report → approve → download', () => {
  test('user completes the full report lifecycle without real backend', async ({ page }) => {
    // Track approval so the content mock can return the updated state on reload.
    let approved = false;

    // ── Workspace context ────────────────────────────────────────────────────
    await page.route('**/workspace/context', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(WORKSPACE_CONTEXT),
      });
    });

    // ── Submit new report ────────────────────────────────────────────────────
    await page.route('**/reports/staging', async (route) => {
      // Only intercept the POST; let other /staging/* sub-routes fall through.
      if (route.request().method() !== 'POST') {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          request_id: REQUEST_ID,
          status: 'accepted',
          quality_gate: 'pending',
          visited_nodes: [],
          exported_formats: [],
          exports: {},
        }),
      });
    });

    // ── Processing status ────────────────────────────────────────────────────
    // Return state='staging' which ProcessingScreen maps to awaiting_reviewer.
    await page.route(`**/reports/${REQUEST_ID}/status`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          request_id: REQUEST_ID,
          state: 'staging',
          quality_gate: 'passed',
          total_nodes: 18,
          current_node: 15,
          is_terminal: false,
          updated_at: new Date().toISOString(),
        }),
      });
    });

    // ── Report content (stateful) ────────────────────────────────────────────
    // Returns staging (reviewable) until approve fires, then returns approved.
    await page.route(`**/reports/${REQUEST_ID}/content`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          approved
            ? makeContent('approved', false)
            : makeContent('staging', true),
        ),
      });
    });

    // ── Approve action ───────────────────────────────────────────────────────
    await page.route(`**/reports/staging/${REQUEST_ID}/approve`, async (route) => {
      approved = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({}),
      });
    });

    // ── Download ─────────────────────────────────────────────────────────────
    await page.route(`**/reports/staging/${REQUEST_ID}/download/**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/markdown',
        body: '# Executive Decision Report\n\nDownload test content.',
      });
    });

    // ═══════════════════════════════════════════════════════════════════════
    // STEP 1: Query Composer — fill form and submit
    // ═══════════════════════════════════════════════════════════════════════
    await page.goto('/#/workspace/new');
    await page.waitForSelector('text=Query Composer');

    // Select project from dropdown.
    await page.locator('select#query-composer-project').selectOption('PRJ-GP-001');

    // Type management question.
    await page.locator('textarea#query-composer-query').fill(
      'What is the current financial position for PRJ-GP-001?',
    );

    // Submit button must be enabled once project + query are filled.
    const submitBtn = page.locator('button:has-text("Generate Report")');
    await expect(submitBtn).toBeEnabled();

    // Hide role switcher — it overlaps buttons fixed at bottom of viewport.
    await hideSwitcher(page);

    // Click submit and wait for the Processing View heading.
    await submitBtn.click();
    await page.waitForSelector('h1:has-text("Generating report")');

    // ═══════════════════════════════════════════════════════════════════════
    // STEP 2: Processing View — verify screen state
    // ═══════════════════════════════════════════════════════════════════════
    await expect(page.locator('h1:has-text("Generating report")')).toBeVisible();

    // Request ID is shown in the sub-header.
    await expect(
      page.locator('p').filter({ hasText: REQUEST_ID }),
    ).toBeVisible();

    // Status banner: state='staging' maps to awaiting_reviewer.
    await expect(
      page.locator('[role="status"]').filter({ hasText: 'Report submitted for review' }),
    ).toBeVisible();

    // Progress bar must be rendered.
    await expect(
      page.locator('div[class*="h-2 w-full rounded-sm"]'),
    ).toBeVisible();

    // Node list must be visible.
    await expect(page.locator('ul li:has-text("Awaiting reviewer")')).toBeVisible();

    // ═══════════════════════════════════════════════════════════════════════
    // STEP 3: Report View — verify executive content is present
    // ═══════════════════════════════════════════════════════════════════════
    await page.goto(`/#/workspace/report/${REQUEST_ID}`);
    await page.waitForSelector('article');

    // Report heading must appear inside the article.
    await expect(
      page.locator('article h1:has-text("Executive Decision Report")'),
    ).toBeVisible();

    // Body text must contain visible content.
    await expect(
      page.locator('article').filter({ hasText: 'Based on available evidence' }),
    ).toBeVisible();

    // Evidence button must be present (evidence list is non-empty).
    await expect(page.locator('button:has-text("Evidence")')).toBeVisible();

    // Awaiting-review status banner must be shown (state='staging').
    await expect(
      page.locator('[role="status"]').filter({ hasText: 'Awaiting review' }),
    ).toBeVisible();

    // ═══════════════════════════════════════════════════════════════════════
    // STEP 4: Approve — action available; export gated until approval
    // ═══════════════════════════════════════════════════════════════════════
    // Approve button visible because can_review=true and state='staging'.
    const approveBtn = page.locator('button:has-text("Approve")');
    await expect(approveBtn).toBeVisible();
    await expect(approveBtn).toBeEnabled();

    // Export button must NOT exist before approval (state is not approved/final).
    await expect(page.locator('button:has-text("Export")')).toHaveCount(0);

    // Hide role switcher again (new page navigation resets DOM).
    await hideSwitcher(page);

    // Click Approve; wait for both the POST response and the content reload.
    const [approveResponse] = await Promise.all([
      page.waitForResponse(
        (res) =>
          res.url().includes(`/reports/staging/${REQUEST_ID}/approve`) &&
          res.request().method() === 'POST',
      ),
      approveBtn.click(),
    ]);
    expect(approveResponse.status()).toBe(200);

    // After reload: review buttons gone (can_review=false on approved content).
    await expect(page.locator('button:has-text("Approve")')).toHaveCount(0);

    // Export button must appear now (state='approved', quality_gate='passed').
    await expect(page.locator('button:has-text("Export")')).toBeVisible();

    // ═══════════════════════════════════════════════════════════════════════
    // STEP 5: Download — export panel opens with enabled download buttons
    // ═══════════════════════════════════════════════════════════════════════
    await page.locator('button:has-text("Export")').click();

    const exportPanel = page
      .locator('aside[aria-label="Detail panel"]')
      .filter({ hasText: 'Export' });
    await expect(exportPanel).toBeVisible();

    // Markdown download button must be enabled (not locked/blocked).
    const mdBtn = exportPanel.locator('button[aria-label="Download Markdown (.md)"]');
    await expect(mdBtn).toBeEnabled();

    // Click download and assert the HTTP request was fired to the correct URL.
    const [downloadRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes(`/reports/staging/${REQUEST_ID}/download/md`) &&
          req.method() === 'GET',
      ),
      mdBtn.click(),
    ]);
    expect(downloadRequest.url()).toContain(
      `/reports/staging/${REQUEST_ID}/download/md`,
    );
  });
});
