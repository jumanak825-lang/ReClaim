import { expect, test } from "@playwright/test";
import { claimViaApi, createLaptopReport, decide, matchIdFor, resetData, signInAs, signOut } from "./helpers";

test.beforeEach(async ({ request }) => {
  await resetData(request);
});

test("reviewer approves a claim with a reason; claimant sees the next step", async ({ page }) => {
  await signInAs(page, "reviewer@harbourview.example");
  await page.getByRole("link", { name: "Claims", exact: true }).click();
  await page.getByRole("link", { name: /Backpack/ }).click();

  await expect(page.getByRole("heading", { name: "AI assistance (not a decision)" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Claimant's answers and evidence" })).toBeVisible();

  await page.getByRole("button", { name: "Approve", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await dialog.getByLabel("Reason (required)").fill("too short");
  await expect(dialog.getByRole("button", { name: "Approve", exact: true })).toBeDisabled();
  await dialog.getByLabel("Reason (required)").fill("Claimant described the contents that we recorded privately.");
  await dialog.getByRole("button", { name: "Approve", exact: true }).click();

  await expect(page.getByText("Approved").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "History" })).toContainText("Claimant described the contents");

  await signOut(page);
  await signInAs(page, "owner@reclaim.example");
  await page.goto("/claims");
  await page.getByRole("link", { name: /Backpack/ }).click();
  await expect(page.getByText("Your claim was approved")).toBeVisible();
  await expect(page.getByRole("link", { name: "Choose collection or delivery" })).toBeVisible();
});

test("escalated claims move to the Escalated tab and can then be decided", async ({ page }) => {
  await signInAs(page, "reviewer@harbourview.example");
  await page.goto("/org/harbourview-airport/claims");
  await page.getByRole("link", { name: /Backpack/ }).click();
  await decide(page, "Escalate", "Answers are vague; needs a second look.");
  await expect(page.getByText("Escalated").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Escalate", exact: true })).toHaveCount(0);

  await page.goto("/org/harbourview-airport/claims?tab=escalated");
  await page.getByRole("link", { name: /Backpack/ }).click();
  await decide(page, "Reject", "Could not confirm the private details.");
  await expect(page.getByText("Not approved").first()).toBeVisible();
});

test("staff without review rights can't see evidence or decide", async ({ page }) => {
  await signInAs(page, "staff@harbourview.example");
  await page.goto("/org/harbourview-airport/claims");
  await page.getByRole("link", { name: /Backpack/ }).click();
  await expect(page.getByText("Only reviewers can see the claimant's evidence and decide claims.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0);
  await expect(page.getByRole("region", { name: /answers and evidence/ })).toHaveCount(0);
});

test("a reviewer from another organisation can't open the claim", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  const claimId = (await (await page.request.get("/api/v1/claims/mine")).json()).data[0].id as string;
  await signOut(page);

  await signInAs(page, "reviewer@grandmeridian.example");
  await page.goto(`/org/grand-meridian-hotel/claims/${claimId}`);
  await expect(page.getByText("We couldn't find this claim in your organisation.")).toBeVisible();
});

test("only one owner can be approved for an item (FR-019)", async ({ page }) => {
  // Two different people claim the same found laptop.
  await signInAs(page, "owner@reclaim.example");
  await createLaptopReport(page);
  const first = await claimViaApi(page, await matchIdFor(page, "Laptop", "Terminal 1"));
  await signOut(page);
  await signInAs(page, "other@reclaim.example");
  await createLaptopReport(page);
  const second = await claimViaApi(page, await matchIdFor(page, "Laptop", "Terminal 1"));
  await signOut(page);

  await signInAs(page, "reviewer@harbourview.example");
  await page.goto(`/org/harbourview-airport/claims/${first}`);
  await decide(page, "Approve", "Matches the recorded sticker and damage.");
  await expect(page.getByText("Approved").first()).toBeVisible();

  // The second claim can't be approved: the UI offers no Approve and says why...
  await page.goto(`/org/harbourview-airport/claims/${second}`);
  await expect(page.getByText(/already approved\. This claim cannot be approved/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Reject", exact: true })).toBeVisible();
  // ...and the server refuses it even if forced.
  const forced = await page.request.post(`/api/v1/claims/${second}/review`, {
    data: { decision: "approved", reason: "Forcing a second approval." },
  });
  expect(forced.status()).toBe(409);
  expect((await forced.json()).error.code).toBe("FOUND_ITEM_ALREADY_CLAIMED");
});
