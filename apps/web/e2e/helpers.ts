import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const API = "http://localhost:8000/api/v1";

export const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);

export async function resetData(request: APIRequestContext) {
  expect((await request.post(`${API}/dev/reset`)).ok()).toBeTruthy();
}

export async function signInAs(page: Page, email: string) {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("reclaim-demo");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/sign-in/);
}

export async function signOut(page: Page) {
  await page.context().clearCookies();
}

/**
 * As the signed-in user, submit the demo "silver laptop at Terminal 1" lost report through the API
 * and wait for the worker to finish matching. Returns the report id.
 */
export async function createLaptopReport(page: Page): Promise<string> {
  const start = new Date(Date.now() - 26 * 3_600_000).toISOString();
  const end = new Date(Date.now() - 24 * 3_600_000).toISOString();
  const res = await page.request.post("/api/v1/reports/lost", {
    data: {
      category: "electronics",
      item_label: "Laptop",
      description: "Silver laptop with a small sticker near the keyboard.",
      lost_at_start: start,
      lost_at_end: end,
      last_location: { label: "Terminal 1, airport" },
      attributes_public: { colour: "silver" },
      attributes_private: { distinctive_mark: "small dent on left corner" },
    },
  });
  expect(res.ok()).toBeTruthy();
  const id = (await res.json()).data.id as string;
  await expect
    .poll(async () => (await (await page.request.get(`/api/v1/reports/${id}`)).json()).data.processing_status, { timeout: 15_000 })
    .toBe("completed");
  return id;
}

/** Id of the signed-in owner's candidate match whose found item is at `locationText`. */
export async function matchIdFor(page: Page, foundLabel: string, locationText?: string): Promise<string> {
  const body = await (await page.request.get("/api/v1/matches/mine")).json();
  const m = (body.data as { id: string; found_item: { item_label: string; approximate_location: string } }[]).find(
    (x) => x.found_item.item_label === foundLabel && (!locationText || x.found_item.approximate_location.includes(locationText)),
  );
  expect(m, `match for ${foundLabel}`).toBeTruthy();
  return m!.id;
}
