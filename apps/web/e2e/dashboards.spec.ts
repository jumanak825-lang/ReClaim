import { expect, test, type Page } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  expect((await request.post("http://localhost:8000/api/v1/dev/reset")).ok()).toBeTruthy();
});

async function signInAs(page: Page, email: string) {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("reclaim-demo");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/sign-in/);
}

function card(page: Page, label: string) {
  return page.locator("div.rounded-lg.border").filter({ has: page.getByText(label, { exact: true }) });
}

test("individual dashboard shows the user's own counts and activity", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  await expect(page.getByRole("heading", { name: "Welcome, Dana Owner" })).toBeVisible();
  await expect(card(page, "Active lost reports")).toContainText("1");
  await expect(card(page, "Claims awaiting review")).toContainText("1");
  await expect(card(page, "Potential matches")).toContainText("not confirmed ownership");
  const activity = page.getByRole("region", { name: "Recent activity" });
  await expect(activity.getByText("Claim submitted")).toBeVisible();
  await expect(page.getByRole("link", { name: "Report lost" })).toHaveAttribute("href", "/report/lost");
});

test("a brand-new user sees the first-report empty state", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Your name").fill("New Person");
  await page.getByLabel("Email").fill(`new-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("a-long-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Start with your first report" })).toBeVisible();
});

test("organisation overview shows cards, demo label and the priority queue", async ({ page }) => {
  await signInAs(page, "reviewer@harbourview.example");
  await expect(page.getByRole("heading", { name: "Harbourview International Airport" })).toBeVisible();
  await expect(card(page, "Active cases")).toContainText("3");
  await expect(card(page, "Pending claims")).toContainText("1");
  await expect(page.getByText("Seeded demo data")).toBeVisible();

  const queue = page.getByRole("region", { name: "Priority queue" });
  await expect(queue.getByRole("listitem")).toHaveCount(3);
  await expect(queue.getByRole("listitem").first()).toContainText("Backpack");
  await expect(queue.getByRole("listitem").first()).toContainText("High priority");
});

test("location selector filters the priority queue and is kept in the URL", async ({ page }) => {
  await signInAs(page, "reviewer@harbourview.example");
  const queue = page.getByRole("region", { name: "Priority queue" });
  await expect(queue.getByRole("listitem")).toHaveCount(3);

  await page.getByRole("combobox", { name: "Location" }).click();
  await page.getByRole("option", { name: "Terminal 1 Lost Property" }).click();
  await expect(page).toHaveURL(/\?location=/);
  await expect(queue.getByRole("listitem")).toHaveCount(1);
  await expect(queue.getByRole("listitem")).toContainText("Terminal 1 Lost Property");

  await page.reload();
  await expect(queue.getByRole("listitem")).toHaveCount(1);

  await page.getByRole("combobox", { name: "Location" }).click();
  await page.getByRole("option", { name: "All locations" }).click();
  await expect(queue.getByRole("listitem")).toHaveCount(3);
});

test("staff assigned to locations see 'All my locations'", async ({ page }) => {
  await signInAs(page, "staff@harbourview.example");
  await expect(page.getByRole("combobox", { name: "Location" })).toContainText("All my locations");
  await expect(page.getByText("Across all your locations")).toBeVisible();
});

test("an unknown location in the URL is ignored", async ({ page }) => {
  await signInAs(page, "reviewer@harbourview.example");
  await page.goto("/org/harbourview-airport?location=00000000-0000-0000-0000-000000000000");
  await expect(page.getByRole("region", { name: "Priority queue" }).getByRole("listitem")).toHaveCount(3);
});
