import { expect, test, type Page } from "@playwright/test";

// 1×1 transparent PNG.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);

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

function yesterdayAt(hour: number) {
  const d = new Date(Date.now() - 86_400_000);
  d.setHours(hour, 0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(hour)}:00`;
}

async function fillSteps1to3(page: Page) {
  await page.getByRole("combobox", { name: "Category" }).click();
  await page.getByRole("option", { name: "Electronics" }).click();
  await page.getByLabel("What is it?").fill("Laptop");
  await page.getByLabel("Describe it").fill("Silver laptop with a small sticker near the keyboard.");
  await page.getByLabel("Main colour").fill("silver");
  await page.getByRole("button", { name: "Continue" }).click();

  await page.getByLabel("Where did you last have it?").fill("Terminal 1, airport");
  await page.getByLabel("Earliest time").fill(yesterdayAt(9));
  await page.getByLabel("Latest time (optional)").fill(yesterdayAt(11));
  await page.getByRole("button", { name: "Continue" }).click();

  await page.locator('input[type="file"]').setInputFiles({ name: "laptop.png", mimeType: "image/png", buffer: PNG });
  await expect(page.getByRole("img", { name: "Photo 1" })).toBeVisible();
  await page.getByLabel("Distinctive marks, stickers or damage").fill("small dent on left corner");
  await page.getByRole("button", { name: "Save and continue" }).click();
}

test("lost report wizard: draft at step 3, suggestions, privacy summary, submit, matches", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  await page.goto("/report/lost");
  await fillSteps1to3(page);

  // Step 4: draft exists (resumable URL) and suggestions load.
  await expect(page).toHaveURL(/\/report\/lost\?id=/);
  await expect(page.getByRole("heading", { name: "Review suggestions" })).toBeVisible();
  await expect(page.getByText(/Suggestions \(basic keyword matching|AI suggestions/)).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();

  // Step 5: privacy summary separates public and private.
  await expect(page.getByText("Can be shown to possible matches")).toBeVisible();
  await expect(page.getByText("Terminal 1, airport")).toBeVisible();
  const privateBox = page.getByText("Private: only you and authorised reviewers").locator("..").locator("..");
  await expect(privateBox).toContainText("Distinctive marks, stickers or damage");
  await expect(privateBox).not.toContainText("small dent");
  await page.getByRole("button", { name: "Submit report" }).click();

  // Detail: processing, then possible matches with the ownership caveat.
  await expect(page).toHaveURL(/\/reports\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: /possible match/ })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("not proof of ownership")).toBeVisible();
  await expect(page.getByRole("region", { name: "Private details" })).toContainText("small dent on left corner");
});

test("step 1 shows errors when required fields are missing", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  await page.goto("/report/lost");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Choose a category.")).toBeVisible();
  await expect(page.getByText("Say what the item is.")).toBeVisible();
  await expect(page.getByLabel("What is it?")).toHaveAttribute("aria-invalid", "true");
});

test("'I'm not sure' allows continuing without a time", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  await page.goto("/report/lost");
  await page.getByRole("combobox", { name: "Category" }).click();
  await page.getByRole("option", { name: "Keys" }).click();
  await page.getByLabel("What is it?").fill("Keys");
  await page.getByLabel("Describe it").fill("Two keys on a red ring.");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Where did you last have it?").fill("Northgate Mall");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Add an approximate time")).toBeVisible();
  await page.getByLabel("I'm not sure").check();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: "Photos and private details" })).toBeVisible();
});

test("a draft survives a reload and is listed in My reports", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  await page.goto("/report/lost");
  await fillSteps1to3(page);
  await expect(page).toHaveURL(/\?id=/);

  await page.reload();
  await expect(page.getByLabel("What is it?")).toHaveValue("Laptop");

  await page.goto("/reports");
  const draft = page.getByRole("link", { name: /Laptop.*Draft/ });
  await expect(draft).toContainText("Continue where you left off");
  await draft.click();
  await expect(page).toHaveURL(/\/report\/lost\?id=/);
});

test("disguised file is rejected by the server", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  await page.goto("/report/lost");
  await page.getByRole("combobox", { name: "Category" }).click();
  await page.getByRole("option", { name: "Bag or luggage" }).click();
  await page.getByLabel("What is it?").fill("Bag");
  await page.getByLabel("Describe it").fill("Blue bag");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Where did you last have it?").fill("Front desk");
  await page.getByLabel("I'm not sure").check();
  await page.getByRole("button", { name: "Continue" }).click();

  await page.locator('input[type="file"]').setInputFiles({
    name: "photo.png",
    mimeType: "image/png",
    buffer: Buffer.from("MZ this is not an image"),
  });
  await expect(page.getByText("isn't a JPEG, PNG or WebP photo")).toBeVisible();
  await expect(page.getByRole("img", { name: "Photo 1" })).toHaveCount(0);
});

async function createLostReport(page: Page, privateMark: string) {
  const res = await page.request.post("/api/v1/reports/lost", {
    data: {
      category: "wallet",
      item_label: "Wallet",
      description: "Brown leather wallet",
      last_location: { label: "Food court" },
      attributes_private: { distinctive_marks: privateMark },
    },
  });
  expect(res.ok()).toBeTruthy();
  return (await res.json()).data.id as string;
}

test("another user can't open someone else's report", async ({ page, context }) => {
  await signInAs(page, "owner@reclaim.example");
  const id = await createLostReport(page, "initials D.O. inside");

  await context.clearCookies();
  await signInAs(page, "other@reclaim.example");
  await page.goto(`/reports/${id}`);
  await expect(page.getByText("We couldn't find this report, or you don't have access to it.")).toBeVisible();
  await expect(page.getByText("initials D.O. inside")).toHaveCount(0);
});

test("owner can withdraw a report after confirming", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  const id = await createLostReport(page, "scratch on clasp");
  await page.goto(`/reports/${id}`);
  await expect(page.getByRole("link", { name: "Edit" })).toHaveAttribute("href", `/report/lost?id=${id}`);

  await page.getByRole("button", { name: "Withdraw" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("Withdraw this report?");
  await page.getByRole("button", { name: "Withdraw report" }).click();
  await expect(page.getByText("Withdrawn", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Withdraw" })).toHaveCount(0);
});

test("My reports filters by type", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  await page.goto("/reports");
  await expect(page.getByRole("link", { name: /Backpack/ })).toBeVisible();
  await page.getByRole("button", { name: "Found" }).click();
  await expect(page).toHaveURL(/\?type=found/);
  await expect(page.getByText("No found reports yet")).toBeVisible();
});
