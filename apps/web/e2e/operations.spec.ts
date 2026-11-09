import { expect, test } from "@playwright/test";
import { decide, resetData, signInAs, signOut } from "./helpers";

test.beforeEach(async ({ request }) => {
  await resetData(request);
});

// One Item cell per visible row (pinned columns render in a separate container).
const gridRows = (page: import("@playwright/test").Page) => page.locator("[role='gridcell'][col-id='item_label']");

test("operations grid: rows in scope, quick search, row opens the case", async ({ page }) => {
  await signInAs(page, "reviewer@harbourview.example");
  await page.getByRole("link", { name: "Operations" }).click();
  await expect(page.getByRole("heading", { name: "Operations" })).toBeVisible();
  await expect(page.getByRole("gridcell", { name: "Backpack" })).toBeVisible();
  const total = await gridRows(page).count();
  expect(total).toBeGreaterThan(1);

  await page.getByLabel("Quick search").fill("backpack");
  await expect(gridRows(page)).toHaveCount(1);
  await page.getByRole("gridcell", { name: "Backpack" }).click();

  await expect(page).toHaveURL(/\/org\/harbourview-airport\/cases\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: "Backpack" })).toBeVisible();
  await expect(page.getByText("Cage 3, shelf B-11")).toBeVisible(); // custodians see the storage reference
  await expect(page.getByRole("region", { name: "Claims" }).getByRole("link")).toHaveCount(1);
  await page.getByRole("region", { name: "Claims" }).getByRole("link").click();
  await expect(page).toHaveURL(/\/org\/harbourview-airport\/claims\//);
});

test("location filter narrows the grid", async ({ page }) => {
  await signInAs(page, "reviewer@harbourview.example");
  await page.goto("/org/harbourview-airport/operations");
  await expect(page.getByRole("gridcell", { name: "Backpack" })).toBeVisible();
  await page.getByRole("combobox", { name: "Location" }).click();
  await page.getByRole("option", { name: "Terminal 1 Lost Property" }).click();
  await expect(page.getByRole("gridcell", { name: "Backpack" })).toHaveCount(0); // backpack is at Terminal 3
  await expect(page.getByRole("gridcell", { name: "Terminal 1 Lost Property" }).first()).toBeVisible();
});

test("staff don't get audit or integrations, and the API refuses them", async ({ page }) => {
  await signInAs(page, "staff@harbourview.example");
  await expect(page.getByRole("link", { name: "Operations" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Audit log" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Integrations" })).toHaveCount(0);
  await page.goto("/org/harbourview-airport/audit");
  await expect(page.getByText("Only reviewers and managers can read the audit log.")).toBeVisible();
  await page.goto("/org/harbourview-airport/integrations");
  await expect(page.getByText("Only organisation managers can manage integrations.")).toBeVisible();
});

test("manager sees Zapier status and can send a test event", async ({ page }) => {
  await signInAs(page, "manager@harbourview.example");
  await page.getByRole("link", { name: "Integrations" }).click();
  await expect(page.getByRole("heading", { name: "Zapier" })).toBeVisible();
  await expect(page.getByText("claim.created")).toBeVisible();
  await page.getByRole("button", { name: "Send test event" }).click();
  await expect(page.getByText(/Test event queued/)).toBeVisible();
});

test("a claim decision appears in the audit log with its reason", async ({ page }) => {
  await signInAs(page, "reviewer@harbourview.example");
  await page.goto("/org/harbourview-airport/claims");
  await page.getByRole("link", { name: /Backpack/ }).click();
  await decide(page, "Approve", "Contents matched what we recorded privately.");
  await expect(page.getByText("Approved").first()).toBeVisible();

  await page.getByRole("link", { name: "Audit log" }).click();
  const row = page.getByRole("row", { name: /claim\.approved/ });
  await expect(row).toContainText("Riya Reviewer");
  await expect(row).toContainText("Contents matched what we recorded privately.");
});

test("another organisation's case is not found", async ({ page }) => {
  await signInAs(page, "reviewer@harbourview.example");
  const cases = await (await page.request.get("/api/v1/me")).json();
  const hvOrg = cases.data.memberships[0].organisation_id as string;
  const rows = await (await page.request.get(`/api/v1/organisations/${hvOrg}/cases?limit=1`)).json();
  const caseId = rows.data[0].id as string;
  await signOut(page);

  await signInAs(page, "reviewer@grandmeridian.example");
  await page.goto(`/org/grand-meridian-hotel/cases/${caseId}`);
  await expect(page.getByText("We couldn't find this case in your organisation or locations.")).toBeVisible();
});
