import { expect, test, type Page } from "@playwright/test";

const PASSWORD = "reclaim-demo";

test.beforeAll(async ({ request }) => {
  // Known state: reseed the in-memory stub API.
  expect((await request.post("http://localhost:8000/api/v1/dev/reset")).ok()).toBeTruthy();
});

async function signIn(page: Page, email: string, password = PASSWORD) {
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("landing page explains the network and links to reporting", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Lost something? Let AI bring it back.");
  await expect(page.getByRole("link", { name: "Report a lost item" })).toHaveAttribute("href", "/report/lost");
  await expect(page.getByRole("link", { name: "Report a found item" })).toHaveAttribute("href", "/report/found");
  await expect(page.getByText("never proof of ownership")).toBeVisible();
});

test("signed-out visitor is sent to sign-in, then back to where they were going", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/sign-in\?next=%2Fdashboard$/);
  await signIn(page, "owner@reclaim.example");
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Welcome, Dana Owner" })).toBeVisible();
});

test("wrong password shows a generic error", async ({ page }) => {
  await page.goto("/sign-in");
  await signIn(page, "owner@reclaim.example", "wrong-password");
  await expect(page.locator("[data-slot=alert]")).toHaveText("Email or password is incorrect.");
  await expect(page).toHaveURL(/\/sign-in/);
});

test("an off-site next parameter is ignored (no open redirect)", async ({ page }) => {
  await page.goto("/sign-in?next=//evil.example/steal");
  await signIn(page, "owner@reclaim.example");
  await expect(page).toHaveURL("http://localhost:3000/dashboard");
});

test("staff land in their organisation and can't open another one", async ({ page }) => {
  await page.goto("/sign-in");
  await signIn(page, "staff@harbourview.example");
  await expect(page).toHaveURL(/\/org\/harbourview-airport$/);
  await expect(page.getByRole("heading", { name: "Harbourview International Airport" })).toBeVisible();

  await page.goto("/org/grand-meridian-hotel");
  await expect(page.getByRole("heading", { name: "You don't have access" })).toBeVisible();
});

test("sign out ends the session", async ({ page }) => {
  await page.goto("/sign-in");
  await signIn(page, "owner@reclaim.example");
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("button", { name: "Dana Owner" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/sign-in$/);

  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/sign-in\?next=/);
});

test("a stale session cookie is caught by the API check", async ({ page, context }) => {
  await context.addCookies([{ name: "reclaim_session", value: "not-a-real-session", url: "http://localhost:3000" }]);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/sign-in\?next=%2Fdashboard$/);
});

test("register creates an account and signs in", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Test Person");
  await page.getByLabel("Email").fill(`test-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("a-long-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Welcome, Test Person" })).toBeVisible();
});

test("register with an existing email gives a non-revealing error", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Someone");
  await page.getByLabel("Email").fill("owner@reclaim.example");
  await page.getByLabel("Password").fill("a-long-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.locator("[data-slot=alert]")).toContainText("We couldn't create an account with these details");
});

test("register validation errors appear next to the field", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Someone");
  await page.getByLabel("Email").fill("someone@example.com");
  await page.getByLabel("Password").fill("short");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByLabel("Password")).toHaveAttribute("aria-invalid", "true");
});
