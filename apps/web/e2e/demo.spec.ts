import { expect, test } from "@playwright/test";
import { PNG, resetData, signInAs, signOut } from "./helpers";

// The demo story from docs/10 §10.3, entirely through the UI, against the real API.
// Lost laptop → AI candidate → private claim → human approval → delivery with PayPal Sandbox (mock)
// → simulated courier → receipt → case closed.
test("demo happy path: report, match, claim, review, pay, deliver", async ({ page, request }) => {
  test.setTimeout(180_000);
  await resetData(request);

  // Act 1: the traveller reports a lost laptop.
  await signInAs(page, "owner@reclaim.example");
  await page.getByRole("main").getByRole("link", { name: "Report lost" }).click();
  await page.getByRole("combobox", { name: "Category" }).click();
  await page.getByRole("option", { name: "Electronics" }).click();
  await page.getByLabel("What is it?").fill("Laptop");
  await page.getByLabel("Describe it").fill("Silver laptop with a small sticker near the keyboard.");
  await page.getByLabel("Main colour").fill("silver");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByLabel("Where did you last have it?").fill("Terminal 1, airport");
  const d = new Date(Date.now() - 25 * 3_600_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  await page.getByLabel("Earliest time").fill(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00`);
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles({ name: "laptop.png", mimeType: "image/png", buffer: PNG });
  await expect(page.getByRole("img", { name: "Photo 1" })).toBeVisible();
  await page.getByLabel("Distinctive marks, stickers or damage").fill("Dent on the left rear corner");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByRole("heading", { name: "Review suggestions" })).toBeVisible();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Submit report" }).click();

  // Act 3: the AI surfaces the airport's found laptop; the score is not ownership proof.
  await expect(page.getByRole("link", { name: "View possible matches" })).toBeVisible({ timeout: 20_000 });
  await page.getByRole("link", { name: "View possible matches" }).click();
  await page.getByRole("link", { name: /Found item: Laptop.*Terminal 1/ }).click();
  await expect(page.getByText("not proof of ownership").first()).toBeVisible();

  // Act 4: verify ownership privately.
  await page.getByRole("link", { name: "Claim this item" }).click();
  await page.getByLabel("Why do you believe this is yours?").fill("I lost my silver laptop at Terminal 1 yesterday.");
  await page.getByLabel(/distinctive marks/i).fill("A blue mountain sticker next to the trackpad and a dent on the left rear corner.");
  await page.getByRole("button", { name: "Submit claim" }).click();
  await expect(page.getByText("Claim submitted")).toBeVisible();
  const claimUrl = page.url().replace("?submitted=1", "");
  const claimId = claimUrl.split("/").pop()!;

  await signOut(page);
  await signInAs(page, "reviewer@harbourview.example");
  await page.goto(`/org/harbourview-airport/claims/${claimId}`);
  await expect(page.getByRole("heading", { name: "AI assistance (not a decision)" })).toBeVisible();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await page.getByRole("alertdialog").getByLabel("Reason (required)").fill("Claimant described the private sticker and damage correctly.");
  await page.getByRole("alertdialog").getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByText("Approved").first()).toBeVisible();
  await page.getByRole("link", { name: "Audit log" }).click();
  await expect(page.getByRole("row", { name: /claim\.approved/ })).toBeVisible();

  // Act 5: the owner chooses delivery and pays with PayPal Sandbox (mocked locally).
  await signOut(page);
  await signInAs(page, "owner@reclaim.example");
  await page.goto("/notifications");
  await page.getByRole("button", { name: /Claim approved/ }).first().click();
  await page.getByRole("link", { name: "Choose collection or delivery" }).click();
  await page.getByLabel(/Have it delivered/).check();
  await page.getByLabel("Recipient name").fill("Dana Owner");
  await page.getByLabel("Address line 1").fill("12 Example Street");
  await page.getByLabel("City", { exact: true }).fill("Dubai");
  await page.getByLabel("Country code").fill("AE");
  await page.getByRole("button", { name: "Continue to price" }).click();
  await expect(page).toHaveURL(/\/recoveries\/[0-9a-f-]+$/);
  const recoveryId = page.url().split("/").pop()!;
  await page.getByRole("button", { name: "Pay with PayPal (Sandbox)" }).click();
  await page.getByRole("link", { name: "Approve payment" }).click();
  await expect(page.getByText("Payment confirmed")).toBeVisible();

  // Act 6: staff dispatch, simulated courier, receipt, case closed.
  await signOut(page);
  await signInAs(page, "staff@harbourview.example");
  await page.goto(`/org/harbourview-airport/recoveries/${recoveryId}`);
  await page.getByRole("button", { name: "Dispatch (simulated courier)" }).click();
  await expect(page.getByText("Tracking reference")).toBeVisible();
  expect((await page.request.post(`/api/v1/dev/recoveries/${recoveryId}/advance-courier`)).ok()).toBeTruthy();

  await signOut(page);
  await signInAs(page, "owner@reclaim.example");
  await page.goto(`/recoveries/${recoveryId}`);
  await page.getByRole("button", { name: "I've received my item" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Confirm received" }).click();
  await expect(page.getByText("Your item is back with you")).toBeVisible();
});
