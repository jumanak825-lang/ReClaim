import { expect, test } from "@playwright/test";

// Individual reporting must work on mobile (docs/02 §2.6): no horizontal page scroll.
for (const path of ["/", "/sign-in", "/register", "/dashboard", "/report/lost", "/reports"]) {
  test(`${path} fits a phone screen`, async ({ page }) => {
    await page.goto(path);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
}
