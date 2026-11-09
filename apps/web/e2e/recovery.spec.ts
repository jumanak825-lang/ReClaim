import { expect, test } from "@playwright/test";
import { approvedBackpackClaim, deliveryViaApi, resetData, signInAs, signOut } from "./helpers";

test.beforeEach(async ({ request }) => {
  await resetData(request);
});

test("collection: staff mark ready, claimant shows a one-time code, staff validate it", async ({ page }) => {
  const claimId = await approvedBackpackClaim(page);
  await page.goto(`/claims/${claimId}`);
  await page.getByRole("link", { name: "Choose collection or delivery" }).click();
  await page.getByLabel(/Collect it/).check();
  await page.getByRole("button", { name: "Confirm" }).click();

  await expect(page).toHaveURL(/\/recoveries\/[0-9a-f-]+$/);
  const recoveryUrl = page.url();
  const recoveryId = recoveryUrl.split("/").pop()!;
  await expect(page.getByRole("region", { name: "Collection" })).toContainText("Terminal 3 Lost Property");
  await expect(page.getByRole("button", { name: "Show pickup code" })).toHaveCount(0); // not ready yet

  await signOut(page);
  await signInAs(page, "staff@harbourview.example");
  await page.goto(`/org/harbourview-airport/recoveries/${recoveryId}`);
  await page.getByRole("button", { name: "Mark ready for pickup" }).click();
  await expect(page.getByLabel("Claimant's pickup code")).toBeVisible();

  await signOut(page);
  await signInAs(page, "owner@reclaim.example");
  await page.goto(recoveryUrl);
  await page.getByRole("button", { name: "Show pickup code" }).click();
  const first = (await page.locator("p.font-mono").textContent())!.trim();
  expect(first).toMatch(/^[A-Z0-9]{4}-[A-Z0-9]{4}$/);
  await page.reload();
  await expect(page.getByText(first)).toHaveCount(0); // the server only keeps a hash

  // Showing it again rotates the code: the first one must stop working.
  await page.getByRole("button", { name: "Show pickup code" }).click();
  const fresh = (await page.locator("p.font-mono").textContent())!.trim();
  expect(fresh).not.toBe(first);

  await signOut(page);
  await signInAs(page, "staff@harbourview.example");
  await page.goto(`/org/harbourview-airport/recoveries/${recoveryId}`);
  await page.getByLabel("Claimant's pickup code").fill(first);
  await page.getByRole("button", { name: "Validate and hand over" }).click();
  await expect(page.getByText("That pickup code isn't valid")).toBeVisible();
  await page.getByLabel("Claimant's pickup code").fill(fresh);
  await page.getByRole("button", { name: "Validate and hand over" }).click();
  await expect(page.getByText("Recovery complete", { exact: true })).toBeVisible();
});

test("delivery: server-priced PayPal Sandbox checkout, dispatch, simulated courier, receipt", async ({ page }) => {
  const claimId = await approvedBackpackClaim(page);
  await page.goto(`/claims/${claimId}/recovery`);
  await page.getByLabel(/Have it delivered/).check();
  await page.getByRole("button", { name: "Continue to price" }).click();
  await expect(page.getByText("Add the recipient's name.")).toBeVisible();
  await page.getByLabel("Recipient name").fill("Dana Owner");
  await page.getByLabel("Address line 1").fill("12 Example Street");
  await page.getByLabel("City", { exact: true }).fill("Dubai");
  await page.getByLabel("Country code").fill("AE");
  await page.getByRole("button", { name: "Continue to price" }).click();

  await expect(page).toHaveURL(/\/recoveries\/[0-9a-f-]+$/);
  const recoveryId = page.url().split("/").pop()!;
  await expect(page.getByRole("region", { name: "Delivery" })).toContainText(/Delivery fee: .*\d/);
  await expect(page.getByText("isn't a reward for the finder")).toBeVisible();

  await page.getByRole("button", { name: "Pay with PayPal (Sandbox)" }).click();
  // The mock checkout is served by the API through the same-origin /api proxy.
  await expect(page).toHaveURL(/\/api\/v1\/dev\/mock-paypal\/checkout\?token=MOCK-/);
  await page.getByRole("link", { name: "Approve payment" }).click();
  await expect(page).toHaveURL(/\/checkout\/paypal\/return\?token=/);
  await expect(page.getByText("Payment confirmed")).toBeVisible();
  await expect(page.getByText("PayPal Sandbox · no real money")).toBeVisible();
  await page.getByRole("link", { name: "Continue to recovery" }).click();
  await expect(page.getByRole("region", { name: "Delivery" })).toContainText("Paid");

  await signOut(page);
  await signInAs(page, "staff@harbourview.example");
  await page.goto(`/org/harbourview-airport/recoveries/${recoveryId}`);
  await expect(page.getByText("Full address hidden")).toBeVisible();
  await expect(page.getByText("12 Example Street")).toHaveCount(0);
  await page.getByRole("button", { name: "Dispatch (simulated courier)" }).click();
  await expect(page.getByText("Tracking reference")).toBeVisible();
  expect((await page.request.post(`/api/v1/dev/recoveries/${recoveryId}/advance-courier`)).ok()).toBeTruthy();

  await signOut(page);
  await signInAs(page, "owner@reclaim.example");
  await page.goto(`/recoveries/${recoveryId}`);
  await expect(page.getByText("In transit").first()).toBeVisible();
  await page.getByRole("button", { name: "I've received my item" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Confirm received" }).click();
  await expect(page.getByText("Your item is back with you")).toBeVisible();
});

test("cancelling at PayPal charges nothing and leaves payment pending", async ({ page }) => {
  const claimId = await approvedBackpackClaim(page);
  const recoveryId = await deliveryViaApi(page, claimId);
  await page.goto(`/recoveries/${recoveryId}`);
  await page.getByRole("button", { name: "Pay with PayPal (Sandbox)" }).click();
  await page.getByRole("link", { name: "Cancel and return" }).click();
  await expect(page.getByText("Payment cancelled")).toBeVisible();
  await page.getByRole("link", { name: "Back to recovery" }).click();
  await expect(page.getByRole("button", { name: "Pay with PayPal (Sandbox)" })).toBeVisible();
});

test("arriving at the return page without approval doesn't mark anything paid", async ({ page }) => {
  const claimId = await approvedBackpackClaim(page);
  const recoveryId = await deliveryViaApi(page, claimId);
  const order = await page.request.post("/api/v1/payments/paypal/create-order", {
    data: { recovery_id: recoveryId, idempotency_key: `test-${Date.now()}` },
  });
  const orderId = (await order.json()).data.paypal_order_id as string;

  // As if PayPal redirected back but the buyer never approved.
  await page.goto(`/checkout/paypal/return?token=${orderId}&recovery_id=${recoveryId}`);
  await expect(page.getByText("Payment not completed")).toBeVisible();
  await page.getByRole("link", { name: "Back to recovery" }).click();
  await expect(page.getByRole("button", { name: "Pay with PayPal (Sandbox)" })).toBeVisible();
});

test("recovery choice waits for approval, and recoveries are private", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  const claimId = (await (await page.request.get("/api/v1/claims/mine")).json()).data[0].id as string;
  await page.goto(`/claims/${claimId}/recovery`);
  await expect(page.getByText("Collection or delivery becomes available once your claim is approved.")).toBeVisible();

  await signOut(page);
  const approved = await approvedBackpackClaim(page);
  const res = await page.request.post(`/api/v1/claims/${approved}/recoveries`, { data: { method: "collection" } });
  const recoveryId = (await res.json()).data.id as string;
  await signOut(page);
  await signInAs(page, "other@reclaim.example");
  await page.goto(`/recoveries/${recoveryId}`);
  await expect(page.getByText("We couldn't find this recovery, or you don't have access to it.")).toBeVisible();
});
