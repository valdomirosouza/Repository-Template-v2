// CUJ-002 — HITL operator journey: queue → approve → request leaves the queue (W15-T4, #391).
//
// The API is mocked at the network layer so the journey runs against the built app alone
// (ci-frontend.yml starts Next and points NEXT_PUBLIC_API_BASE_URL at localhost:8000, which
// nothing serves; Playwright's route interception answers instead). Synthetic ids only.
import { expect, test } from "@playwright/test";

const API = "**/v1/hitl/requests";

const pending = [
  {
    requestId: "00000000-0000-0000-0000-00000000c0de",
    agentId: "agent-00000000-0000-0000-0000-000000000001",
    actionType: "generate-report",
    riskScore: 0.55,
    contextSummary: "Agent proposes generating a synthetic orders report (PII-masked).",
    createdAt: new Date().toISOString(),
    expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
  },
];

test("operator approves a pending request and it leaves the queue", async ({ page }) => {
  let listCalls = 0;
  const decisions: Array<{ url: string; body: unknown }> = [];

  await page.route(API, async (route) => {
    listCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "X-Total-Count": String(pending.length) },
      body: JSON.stringify(pending),
    });
  });
  await page.route(`${API}/*/decision`, async (route) => {
    decisions.push({ url: route.request().url(), body: route.request().postDataJSON() });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        request_id: pending[0].requestId,
        decision: "APPROVED",
        message: "Decision APPROVED recorded.",
      }),
    });
  });

  await page.goto("/hitl");
  await expect(page.getByRole("heading", { name: "HITL Approval Queue" })).toBeVisible();
  await expect(page.getByText("1 pending request")).toBeVisible();
  await expect(page.getByText("generate-report")).toBeVisible();

  const approve = page.getByRole("button", { name: /approve/i });
  await expect(approve).toBeDisabled(); // rationale is required before a decision
  await page.getByPlaceholder("Rationale (required)").fill("Verified against approved scope.");
  await expect(approve).toBeEnabled();
  await approve.click();

  await expect(page.getByText("No pending requests.")).toBeVisible();
  expect(listCalls).toBeGreaterThanOrEqual(1);
  expect(decisions).toHaveLength(1);
  expect(decisions[0].url).toContain(pending[0].requestId);
  expect(decisions[0].body).toMatchObject({ decision: "APPROVED" });
});

test("an API failure is shown, not swallowed", async ({ page }) => {
  await page.route(API, (route) => route.fulfill({ status: 503, body: "unavailable" }));
  await page.goto("/hitl");
  await expect(page.getByText(/^Error:/)).toBeVisible();
});
