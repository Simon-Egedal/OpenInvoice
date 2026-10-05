import { test, expect } from "@playwright/test";
import { invoiceTotals, lineAmount, minAmount, formatMoney } from "../src/lib/money";

test("line rounding and VAT agree with backend half-up rules", () => {
  const lines = [{quantity: "0.5", unit_price: "0.01", tax_rate: "25"}, {quantity: "0.5", unit_price: "0.01", tax_rate: "25"}];
  expect(lineAmount(lines[0])).toBe("0.01");
  expect(invoiceTotals(lines)).toEqual({subtotal: "0.02", tax: "0.00", total: "0.02"});
  expect(invoiceTotals([{quantity: "3", unit_price: "0.10", tax_rate: "25"}])).toEqual({subtotal: "0.30", tax: "0.08", total: "0.38"});
});

test("large amounts stay exact and allocation never exceeds balance", () => {
  expect(invoiceTotals([{quantity: "1.001", unit_price: "99999999.99", tax_rate: "0"}]).total).toBe("100099999.99");
  expect(minAmount("90071992547409.92", "90071992547409.91")).toBe("90071992547409.91");
  expect(formatMoney("-1000.50")).toBe("-1,000.50");
});
