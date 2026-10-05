import { test, expect } from "@playwright/test";

test.beforeEach(async ({page}) => {
  await page.goto("/auth");
  await page.getByLabel("Email", {exact: true}).fill("browser@example.com");
  await page.getByLabel("Password", {exact: true}).fill("Browser test password 123");
  await page.getByRole("button", {name: "Sign in", exact: true}).click();
  await expect(page).toHaveURL("http://127.0.0.1:13000/");
});

test("create, issue, queue delivery, record partial payment and reconcile", async ({page}) => {
  await page.goto("/invoices/new");
  await page.getByLabel("Customer", {exact: true}).selectOption({label: "Browser customer"});
  await page.getByLabel("Description", {exact: true}).fill("Browser workflow service");
  await page.getByLabel("Unit price", {exact: true}).fill("100.00");
  await page.getByLabel("VAT rate", {exact: true}).fill("0");
  await page.getByRole("button", {name: "Save draft", exact: true}).click();
  await expect(page).toHaveURL(/\/invoices\/[0-9a-f-]+$/, {timeout: 20000});
  await expect(page.getByRole("heading", {level: 1})).toHaveText(/INV-\d{6}/);
  const invoiceId = page.url().split("/").pop()!;
  await page.getByRole("button", {name: "Issue invoice", exact: true}).click();
  await expect(page.getByRole("button", {name: "Issue invoice", exact: true})).toHaveCount(0);
  await page.getByRole("button", {name: "Send invoice", exact: true}).click();
  await page.reload();
  await expect(page.getByRole("cell", {name: "queued", exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Mark as paid", exact: true}).click();
  await page.getByRole("button", {name: "Custom amount", exact: true}).click();
  await page.getByLabel("Amount (DKK)", {exact: true}).fill("40.00");
  await page.getByRole("button", {name: "Save payment", exact: true}).click();
  await expect(page.locator(".page-head .status")).toHaveText("partially paid");
  const sync = await page.request.post("http://127.0.0.1:18000/api/v1/banking/sync");
  expect(sync.ok()).toBeTruthy();
  const transactions = await (await page.request.get("http://127.0.0.1:18000/api/v1/banking/transactions")).json();
  const receipt = transactions.find((transaction: {direction: string; unmatched_amount: string}) => transaction.direction === "credit" && Number(transaction.unmatched_amount) >= 60);
  const match = await page.request.post(`http://127.0.0.1:18000/api/v1/invoices/${invoiceId}/link-transaction`, {data: {transaction_id: receipt.id, amount: "60.00"}});
  expect(match.ok()).toBeTruthy();
  await page.reload();
  await expect(page.locator(".page-head .status")).toHaveText("paid");
  const pdf = await page.request.get(`http://127.0.0.1:18000/api/v1/invoices/${invoiceId}/pdf`);
  expect(pdf.headers()["content-type"]).toContain("application/pdf");
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
});

test("invoice list shows API failure and recovers after retry", async ({page}) => {
  await page.route("**/api/v1/invoices?limit=50**", route => route.fulfill({status: 503, contentType: "application/json", body: JSON.stringify({detail: "Temporary invoice service failure"})}));
  await page.goto("/invoices");
  await expect(page.locator(".error-text[role=alert]")).toContainText("Temporary invoice service failure");
  await page.unroute("**/api/v1/invoices?limit=50**");
  await page.getByRole("button", {name: "Retry", exact: true}).click();
  await expect(page.locator(".error-text[role=alert]")).toHaveCount(0);
  await expect(page.getByRole("heading", {name: "Invoices", exact: true})).toBeVisible();
});

test("receive original PDF, reject with reason, resubmit and approve", async ({page}) => {
  const unique = Date.now().toString();
  const supplier = await page.request.post("http://127.0.0.1:18000/api/v1/suppliers", {data: {name: `Browser supplier ${unique}`, email: "supplier@example.com"}});
  expect(supplier.ok()).toBeTruthy();
  await page.goto("/invoices/receive");
  await page.getByLabel("Search suppliers", {exact: true}).fill(`Browser supplier ${unique}`);
  await page.getByLabel("Supplier", {exact: true}).selectOption({label: `Browser supplier ${unique}`});
  await page.getByLabel("Invoice number", {exact: true}).fill(`SUP-${unique}`);
  await page.getByLabel("Due date", {exact: true}).fill("2099-01-01");
  await page.getByLabel("Line description", {exact: true}).fill("Supplier service");
  await page.getByLabel("Net amount", {exact: true}).fill("100.00");
  await page.getByLabel("Invoice PDF (up to 20 MB)", {exact: true}).setInputFiles({name: "original-supplier.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4\nBrowser original document\n%%EOF")});
  await page.getByRole("button", {name: "Save received invoice", exact: true}).click();
  await expect(page).toHaveURL(/\/invoices\/[0-9a-f-]+$/, {timeout: 20000});
  const original = await page.request.get(await page.getByRole("link", {name: "original-supplier.pdf", exact: true}).getAttribute("href") ?? "");
  expect((await original.body()).toString()).toContain("Browser original document");
  await page.getByRole("button", {name: "Submit for approval", exact: true}).click();
  await page.getByLabel("Decision reason", {exact: true}).fill("Supplier needs correction");
  await page.getByRole("button", {name: "Reject", exact: true}).click();
  await expect(page.locator(".page-head .status")).toHaveText("rejected");
  await expect(page.getByText(/rejected · .*Supplier needs correction/)).toBeVisible();
  await page.getByRole("button", {name: "Submit for approval", exact: true}).click();
  await page.getByRole("button", {name: "Approve", exact: true}).click();
  await expect(page.locator(".page-head .status")).toHaveText("approved");
});

test("import customers and download financial exports", async ({page}) => {
  const name = `Imported browser customer ${Date.now()}`;
  await page.goto("/data");
  await page.getByLabel("CSV file", {exact: true}).setInputFiles({name: "customers.csv", mimeType: "text/csv", buffer: Buffer.from(`name,email\n${name},imported@example.com\n`)});
  await page.getByRole("button", {name: "Import records", exact: true}).click();
  await expect(page.getByRole("status")).toHaveText("1 records imported.");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", {name: "Export invoices", exact: true}).click();
  expect((await downloadPromise).suggestedFilename()).toBe("invoices.csv");
  await page.goto("/customers");
  await expect(page.getByRole("cell", {name, exact: true})).toBeVisible();
});
