import { expect, test } from "@playwright/test";

// Individual reporting must work on mobile (docs/02 §2.6): no horizontal page scroll.
for (const path of ["/", "/sign-in", "/register", "/dashboard", "/report/lost", "/report/found", "/reports", "/matches", "/claims", "/notifications"]) {
  test(`${path} fits a phone screen`, async ({ page }) => {
    await page.goto(path);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
}

test("operations shows card rows instead of the grid on a phone", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile", "phone layout only");
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill("reviewer@harbourview.example");
  await page.getByLabel("Password").fill("reclaim-demo");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/sign-in/);
  await page.goto("/org/harbourview-airport/operations");
  await expect(page.getByRole("list", { name: "Cases" }).getByRole("link", { name: /Backpack/ })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
