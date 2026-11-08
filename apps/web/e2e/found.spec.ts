import { expect, test, type Page } from "@playwright/test";

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

async function pick(page: Page, combobox: string, option: string) {
  await page.getByRole("combobox", { name: combobox }).click();
  await page.getByRole("option", { name: option }).click();
}

async function itemStep(page: Page, category: string, label: string, description: string) {
  await pick(page, "Category", category);
  await page.getByLabel("What is it?").fill(label);
  await page.getByLabel("Describe it").fill(description);
}

test("finder who keeps the item: full wizard to submitted report", async ({ page }) => {
  await signInAs(page, "finder@reclaim.example");
  await page.goto("/report/found");
  await expect(page.getByText("Keep it safe to share")).toBeVisible();
  await itemStep(page, "Wallet or purse", "Wallet", "Brown leather wallet, folded.");
  await page.locator('input[type="file"]').setInputFiles({ name: "wallet.png", mimeType: "image/png", buffer: PNG });
  await expect(page.getByRole("img", { name: "Photo 1" })).toBeVisible();
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  // Individuals don't get the staff-only custody option.
  await expect(page.getByLabel("Our organisation is holding it")).toHaveCount(0);
  await page.getByLabel("I have the item").check();
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  await page.getByLabel("Where did you find it?").fill("Bench outside Gate B12");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page).toHaveURL(/\/report\/found\?id=.*&step=4/);
  await expect(page.getByRole("heading", { name: "Visible details" })).toBeVisible();
  await page.getByLabel("Main colour").fill("brown");
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  await expect(page.getByLabel("Storage reference (staff only)")).toHaveCount(0);
  await page.getByLabel("Contents or attached items").fill("library card for J. Smith");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByRole("heading", { name: "Review suggestions" })).toBeVisible();
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  await expect(page.getByText("Can be shown to possible owners")).toBeVisible();
  await expect(page.getByText("Bench outside Gate B12")).toBeVisible();
  await expect(page.getByText("library card for J. Smith")).toHaveCount(0);
  await page.getByRole("button", { name: "Submit report" }).click();

  await expect(page).toHaveURL(/\/reports\/[0-9a-f-]+$/);
  await expect(page.getByText("Found report")).toBeVisible();
  await expect(page.getByText("The finder has it")).toBeVisible();
  await expect(page.getByRole("region", { name: "Private details" })).toContainText("library card for J. Smith");
});

test("custody is locked once the draft is saved", async ({ page }) => {
  await signInAs(page, "finder@reclaim.example");
  await page.goto("/report/found");
  await itemStep(page, "Umbrella", "Umbrella", "Green folding umbrella.");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByLabel("I have the item").check();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByLabel("Where did you find it?").fill("Bus stop");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByRole("heading", { name: "Visible details" })).toBeVisible();

  await page.getByRole("button", { name: "Back" }).click();
  await page.getByRole("button", { name: "Back" }).click();
  await expect(page.getByText("This can't be changed after the draft is saved")).toBeVisible();
  await expect(page.getByRole("radio")).toHaveCount(0);
});

test("finder hands the item to an organisation", async ({ page }) => {
  await signInAs(page, "other@reclaim.example");
  await page.goto("/report/found");
  await itemStep(page, "Glasses", "Sunglasses", "Black sunglasses in a hard case.");
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  await page.getByLabel("I handed it to an organisation").check();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByText("Choose the organisation.")).toBeVisible();
  await pick(page, "Organisation", "Grand Meridian Hotel");
  await pick(page, "Location", "Front Desk");
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  await expect(page.getByText(/Listed at\s+Front Desk/)).toBeVisible();
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByRole("heading", { name: "Visible details" })).toBeVisible();
  await page.getByRole("button", { name: "Continue", exact: true }).click(); // visible details
  await expect(page.getByLabel("Storage reference (staff only)")).toHaveCount(0);
  await page.getByRole("button", { name: "Save and continue" }).click(); // private details
  await page.getByRole("button", { name: "Continue", exact: true }).click(); // suggestions
  await page.getByRole("button", { name: "Submit report" }).click();

  await expect(page).toHaveURL(/\/reports\/[0-9a-f-]+$/);
  await expect(page.getByText("Front Desk, Grand Meridian Hotel")).toBeVisible();
  await expect(page.getByText("Handed to an organisation")).toBeVisible();
});

test("staff log a found item from the org portal, with a private storage reference", async ({ page }) => {
  await signInAs(page, "staff@harbourview.example");
  await page.getByRole("link", { name: "Log found item" }).click();
  await expect(page).toHaveURL(/\/report\/found\?org=harbourview-airport/);

  await itemStep(page, "Phone", "Phone", "Black phone in a clear case.");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByLabel("Our organisation is holding it")).toBeChecked();
  await expect(page.getByRole("combobox", { name: "Organisation" })).toContainText("Harbourview International Airport");
  await pick(page, "Location", "Terminal 1 Lost Property");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByRole("heading", { name: "Visible details" })).toBeVisible();
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  await page.getByLabel("Storage reference (staff only)").fill("Shelf C4, bin 12");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByText("Storage reference (your organisation only)")).toBeVisible();
  await page.getByRole("button", { name: "Submit report" }).click();

  await expect(page).toHaveURL(/\/reports\/[0-9a-f-]+$/);
  await expect(page.getByText("Terminal 1 Lost Property, Harbourview International Airport")).toBeVisible();
  await expect(page.getByRole("region", { name: "Private details" })).toContainText("Shelf C4, bin 12");
});

test("a possible owner sees the found item's public view only", async ({ page }) => {
  await signInAs(page, "owner@reclaim.example");
  const matches = await (await page.request.get("/api/v1/matches/mine")).json();
  const foundId = matches.data.find((m: { found_item: { item_label: string } }) => m.found_item.item_label === "Backpack")
    .found_item.report_id as string;

  await page.goto(`/reports/${foundId}`);
  await expect(page.getByText("You're seeing the public details of this report")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Backpack" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Private details" })).toHaveCount(0);
  await expect(page.getByText("Cage 3, shelf B-11")).toHaveCount(0);
  await expect(page.getByText("paperback novel")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Withdraw" })).toHaveCount(0);
});

test("found time can't be in the future", async ({ page }) => {
  await signInAs(page, "finder@reclaim.example");
  await page.goto("/report/found");
  await itemStep(page, "Keys", "Keys", "Single key on a blue fob.");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByLabel("I have the item").check();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByLabel("Where did you find it?").fill("Car park level 2");
  await page.getByLabel("When did you find it?").fill("2099-01-01T10:00");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByText("This can't be in the future.")).toBeVisible();
});
