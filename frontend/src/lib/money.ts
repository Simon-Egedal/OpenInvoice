/** Decimal arithmetic matches Python ROUND_HALF_UP; API amounts stay strings. */
export function scaled(value: string, places = 2): bigint {
  const match = /^(-?)(\d+)(?:\.(\d*))?$/.exec(value.trim());
  if (!match) return 0n;
  const fraction = match[3] ?? "";
  let result = BigInt(match[2]) * 10n ** BigInt(places) + BigInt((fraction.slice(0, places).padEnd(places, "0")) || "0");
  if (fraction.length > places && fraction[places] >= "5") result += 1n;
  return match[1] ? -result : result;
}

export function decimal(value: bigint, places = 2): string {
  const digits = (value < 0n ? -value : value).toString().padStart(places + 1, "0");
  return `${value < 0n ? "-" : ""}${digits.slice(0, -places)}.${digits.slice(-places)}`;
}

function roundDivision(value: bigint, denominator: bigint): bigint {
  const sign = value < 0n ? -1n : 1n;
  return sign * ((sign * value + denominator / 2n) / denominator);
}

export type MoneyLine = {quantity: string; unit_price: string; tax_rate: string};
export function lineAmount(line: MoneyLine): string {
  return decimal(roundDivision(scaled(line.quantity, 3) * scaled(line.unit_price), 1000n));
}
export function invoiceTotals(lines: MoneyLine[]) {
  let subtotal = 0n;
  let tax = 0n;
  for (const line of lines) {
    const amount = scaled(lineAmount(line));
    subtotal += amount;
    tax += roundDivision(amount * scaled(line.tax_rate, 3), 100000n);
  }
  return {subtotal: decimal(subtotal), tax: decimal(tax), total: decimal(subtotal + tax)};
}
export function minAmount(a: string, b: string): string { return decimal(scaled(a) < scaled(b) ? scaled(a) : scaled(b)); }
export function formatMoney(value: string): string {
  const normalized = decimal(scaled(value));
  const [whole, cents] = normalized.split(".");
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${cents}`;
}
