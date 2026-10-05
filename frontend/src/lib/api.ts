export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}/api/v1${path}`, { ...init, credentials: "include", headers: { "Content-Type": "application/json", ...init.headers } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail ?? `Request failed (${response.status})`); }
  if (response.status === 204) return undefined as T;
  return response.json();
}
export type Invoice = { id:string; invoice_number:string; invoice_type:"incoming"|"outgoing"; status:string; customer_id:string|null; supplier_id:string|null; issue_date:string; due_date:string; currency:string; subtotal:string; tax_amount:string; total:string; notes:string|null };
export type Party = { id:string; name:string; email:string|null; phone:string|null; address:string|null; postal_code:string|null; city:string|null; country:string; vat_number:string|null; payment_information:string|null; notes:string|null };
export type SetupStatus = {
  complete: boolean;
  applied: boolean;
  database_mode: string | null;
  has_organization: boolean;
  has_admin: boolean;
  organization_id?: string | null;
  organization_name?: string | null;
};
export type Organization = {
  id: string;
  name: string;
  country: string;
  currency: string;
  logo_key?: string | null;
  logo_url?: string | null;
};

