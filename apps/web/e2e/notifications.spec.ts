import { expect, test } from "@playwright/test";
import { approveViaApi, createLaptopReport, resetData, signInAs, signOut } from "./helpers";

test.beforeEach(async ({ request }) => {
  await resetData(request);
});

test("unread badge, opening a notification marks it read and goes to the item", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  await createLaptopReport(page); // seeded notifications start read; a new match adds unread ones
  await page.reload();
  const bell = page.getByRole("link", { name: /^Notifications, \d+ unread$/ });
  await expect(bell).toBeVisible();
  const before = Number((await bell.getAttribute("aria-label"))!.match(/(\d+) unread/)![1]);

  await bell.click();
  await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
  await page.getByRole("button", { name: /Potential match found.*\(unread\)/ }).first().click();
  await expect(page).toHaveURL(/\/matches\/[0-9a-f-]+$/);

  await page.goto("/notifications");
  const after = before - 1;
  await expect(page.getByRole("link", { name: after ? `Notifications, ${after} unread` : "Notifications" })).toBeVisible();
  await page.getByRole("button", { name: "Mark all as read" }).click();
  await expect(page.getByRole("link", { name: "Notifications", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark all as read" })).toHaveCount(0);
});

test("a claim decision notifies the claimant and links to the claim", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  const claimId = (await (await page.request.get("/api/v1/claims/mine")).json()).data[0].id as string;
  await signOut(page);
  await signInAs(page, "reviewer@harbourview.example");
  await approveViaApi(page, claimId);
  await signOut(page);

  await signInAs(page, "owner@reclaim.example");
  await page.goto("/notifications");
  await page.getByRole("button", { name: /Claim approved/ }).click();
  await expect(page).toHaveURL(new RegExp(`/claims/${claimId}$`));
  await expect(page.getByText("Your claim was approved")).toBeVisible();
});

test("staff notifications open in the organisation portal", async ({ page }) => {
  await signInAs(page, "reviewer@harbourview.example");
  await page.goto("/notifications");
  await page.getByRole("button", { name: /New claim to review/ }).first().click();
  await expect(page).toHaveURL(/\/org\/harbourview-airport\/claims\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: "AI assistance (not a decision)" })).toBeVisible();
});
