import { expect, test } from "@playwright/test";
import { PNG, createLaptopReport, matchIdFor, resetData, signInAs, signOut } from "./helpers";

test.beforeEach(async ({ request }) => {
  await resetData(request);
});

test("owner reviews a match and submits a private claim", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  await createLaptopReport(page);

  await page.goto("/matches");
  const card = page.getByRole("link", { name: /Found laptop.*Terminal 1/ });
  await expect(card).toContainText("AI relevance");
  await expect(card).toContainText("not proof of ownership");
  await card.click();

  await expect(page.getByRole("heading", { name: "Why this may match" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your lost report" })).toBeVisible();
  // Hidden attributes and storage location never reach the owner before approval.
  for (const secret of ["Cage 2", "blue mountain sticker", "dent on the left rear corner"]) {
    await expect(page.getByText(secret)).toHaveCount(0);
  }

  await page.getByRole("link", { name: "Claim this item" }).click();
  await expect(page.getByText("The finder never sees them")).toBeVisible();
  await page.getByRole("button", { name: "Submit claim" }).click();
  await expect(page.getByText("Tell us why you believe this is yours.")).toBeVisible();

  await page.getByLabel("Why do you believe this is yours?").fill("I lost my laptop at Terminal 1 yesterday morning.");
  await page.getByLabel(/distinctive marks/i).fill("Blue mountain sticker by the trackpad and a dent on the back left corner.");
  await page.getByRole("checkbox").nth(1).check();
  await page.locator('input[type="file"]').setInputFiles({ name: "receipt.png", mimeType: "image/png", buffer: PNG });
  await expect(page.getByRole("img", { name: "Photo 1" })).toBeVisible();
  await page.getByRole("button", { name: "Submit claim" }).click();

  await expect(page).toHaveURL(/\/claims\/[0-9a-f-]+\?submitted=1/);
  await expect(page.getByText("Claim submitted")).toBeVisible();
  await expect(page.getByText("Pending review").first()).toBeVisible();
  const priv = page.getByRole("region", { name: "Your private answers and evidence" });
  await expect(priv).toContainText("Blue mountain sticker");
  await expect(priv).toContainText("I don't remember");
  await expect(priv.getByRole("img", { name: "Claim evidence" })).toBeVisible();

  await page.goto("/claims");
  await expect(page.getByRole("link", { name: /Laptop.*Pending review/ })).toBeVisible();
});

test("'Not my item' dismisses a candidate after confirmation", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  await createLaptopReport(page);
  const tabletMatch = await matchIdFor(page, "Tablet");

  await page.goto(`/matches/${tabletMatch}`);
  await page.getByRole("button", { name: "Not my item" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("Dismiss this match?");
  await page.getByRole("alertdialog").getByRole("button", { name: "Not my item" }).click();
  await expect(page).toHaveURL(/\/matches$/);
  await expect(page.getByRole("link", { name: /Found tablet/ })).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Found laptop/ }).first()).toBeVisible();
});

test("another user can't open someone's claim", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  const claims = await (await page.request.get("/api/v1/claims/mine")).json();
  const claimId = claims.data[0].id as string;

  await signOut(page);
  await signInAs(page, "other@reclaim.example");
  await page.goto(`/claims/${claimId}`);
  await expect(page.getByText("We couldn't find this claim, or you don't have access to it.")).toBeVisible();
});

test("claimant adds evidence to a pending claim", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  await page.goto("/claims");
  await page.getByRole("link", { name: /Backpack/ }).click();
  await expect(page.getByText("Waiting for review")).toBeVisible();

  await page.getByLabel("Note for the reviewer (optional)").fill("It has a red zip pull I replaced last year.");
  await page.getByRole("button", { name: "Add evidence" }).click();
  await expect(page.getByText("Evidence added.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Your private answers and evidence" })).toContainText("red zip pull I replaced");
});

test("an already-claimed match links to the claim instead of a new one", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  const backpackMatch = await matchIdFor(page, "Backpack");
  await page.goto(`/matches/${backpackMatch}/claim`);
  await expect(page.getByText("You've already claimed this item.")).toBeVisible();
  await page.getByRole("link", { name: "View your claim" }).click();
  await expect(page).toHaveURL(/\/claims\//);
});

test("rate-limited sign-in tells the user how long to wait", async ({ page }) => {
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({
      status: 429,
      headers: { "Retry-After": "42" },
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "RATE_LIMITED", message: "Too many requests.", details: { retry_after_seconds: 42 } },
        meta: { request_id: "test", next_cursor: null },
      }),
    }),
  );
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill("owner@reclaim.example");
  await page.getByLabel("Password").fill("reclaim-demo");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("[data-slot=alert]")).toHaveText("Too many attempts. Try again in 42 seconds.");
});
