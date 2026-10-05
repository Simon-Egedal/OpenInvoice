export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}/api/v1${path}`, { ...init, credentials: "include", headers: { "Content-Type": "application/json", ...init.headers } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail ?? `Request failed (${response.status})`); }
  if (response.status === 204) return undefined as T;
  return response.json();
}
export type Invoice = {
  id: string;
  organization_id?: string;
  organization_name?: string | null;
  organization_logo_url?: string | null;
  recipient_name?: string | null;
  recipient_email?: string | null;
  recipient_phone?: string | null;
  recipient_address?: string | null;
  recipient_postal_code?: string | null;
  recipient_city?: string | null;
  recipient_country?: string | null;
  recipient_vat_number?: string | null;
  recipient?: Party | null;
  invoice_number: string;
  invoice_type: "incoming" | "outgoing";
  status: string;
  customer_id: string | null;
  supplier_id: string | null;
  issue_date: string;
  due_date: string;
  currency: string;
  subtotal: string;
  tax_amount: string;
  total: string;
  paid_amount: string;
  due_amount: string;
  notes: string | null;
};

export type InvoicePayment = {
  id: string;
  invoice_id: string;
  amount: string;
  payment_date: string;
  payment_method: string;
  reference: string | null;
  notes: string | null;
  created_at: string;
};

export type InvoiceMatch = {
  id: string;
  invoice_id: string;
  transaction_id: string;
  amount: string;
  confidence: string;
  confirmed: boolean;
  created_at: string;
  transaction_booked_at?: string | null;
  transaction_description?: string | null;
  transaction_counterparty?: string | null;
  transaction_amount?: string | null;
  transaction_currency?: string | null;
  transaction_reference?: string | null;
};

export type LinkableTransaction = {
  id: string;
  booked_at: string;
  description: string;
  counterparty: string | null;
  amount: string;
  currency: string;
  reference: string | null;
  matched_amount: string;
  available_amount: string;
};

export type MatchedInvoiceSummary = {
  match_id: string;
  invoice_id: string;
  invoice_number: string;
  amount: string;
  invoice_total: string;
  invoice_status: string;
};

export type BankTransactionItem = {
  id: string;
  booked_at: string;
  description: string;
  counterparty: string;
  amount: string;
  direction: "credit" | "debit";
  currency: string;
  reference: string | null;
  matched_amount?: string;
  unmatched_amount?: string;
  matches?: MatchedInvoiceSummary[];
};

export type Party = { id:string; name:string; email:string|null; phone:string|null; address:string|null; postal_code:string|null; city:string|null; country:string; vat_number:string|null; payment_information:string|null; notes:string|null };
export type Product = { id: string; name: string; unit_price: string };
export type CurrentUser = { id: string; email: string; full_name: string };
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
export type InfrastructureConfig = {
  can_manage: boolean;
  database_mode: "bundled" | "external";
  database_host: string;
  database_port: number;
  database_name: string;
  database_username: string;
  database_ssl: boolean;
  has_database_password: boolean;
  email_provider: "console" | "smtp";
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_from: string;
  smtp_use_tls: boolean;
  has_smtp_password: boolean;
  storage_provider: "local" | "s3";
  s3_endpoint_url: string;
  s3_bucket: string;
  s3_access_key_id: string;
  s3_region: string;
  has_s3_secret: boolean;
  banking_provider: "mock" | "enable_banking";
  enable_banking_app_id: string;
  enable_banking_private_key_path: string;
  session_cookie_secure: boolean;
  restart_required: boolean;
};
