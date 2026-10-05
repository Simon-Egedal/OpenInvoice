"use client";
import { formatMoney, scaled } from "@/lib/money";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api, Organization, Product } from "@/lib/api";

import { Pagination } from "@/components/pagination";

export default function Products() {
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<Product[]>([]);
  const [currency, setCurrency] = useState("DKK");
  const [name, setName] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true); setError("");
    try {
      const [products, orgs] = await Promise.all([
        api<Product[]>(`/products?limit=50&offset=${page*50}`),
        api<Organization[]>("/organizations"),
      ]);
      setItems(products);
      if (orgs[0]?.currency) setCurrency(orgs[0].currency);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load products");
    } finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, [page]);

  async function createProduct(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const item = await api<Product>("/products", {
        method: "POST",
        body: JSON.stringify({ name, unit_price: unitPrice.replace(",", ".") }),
      });
      await load();
      setName("");
      setUnitPrice("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save product");
    } finally {
      setSaving(false);
    }
  }

  async function removeProduct(item: Product) {
    try {
      await api<void>(`/products/${item.id}`, { method: "DELETE" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete product");
    }
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Products</h1>
          <p className="page-description">Save frequently invoiced products and services for quick reuse.</p>
        </div>
        <Link className="button" href="/invoices/new">Create invoice</Link>
      </header>

      <form onSubmit={createProduct} className="form-grid" style={{ maxWidth: 800, marginBottom: 32, alignItems: "end" }}>
        <div className="field">
          <label htmlFor="product-name">Product or service name</label>
          <input id="product-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} required />
        </div>
        <div className="field">
          <label htmlFor="product-price">Unit price ({currency})</label>
          <input id="product-price" type="number" min="0" step="0.01" value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} required />
        </div>
        <div className="field full" style={{ display: "flex", justifyContent: "flex-end" }}>
          <button className="button button-primary" disabled={saving}><Plus size={14} />{saving ? "Savingâ€¦" : "Add product"}</button>
        </div>
      </form>

      <Pagination page={page} count={items.length} busy={loading} onPage={setPage}/>{loading && <p role="status">Loading products…</p>}{error && <p className="error-text" role="alert">{error} <button className="button" onClick={load}>Retry</button></p>}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Product or service</th><th style={{ textAlign: "right" }}>Unit price</th><th style={{ width: 48 }} /></tr></thead>
          <tbody>
            {items.length === 0 ? (
              <tr><td colSpan={3} className="empty">No saved products yet. Add one above to use it on invoices.</td></tr>
            ) : items.map((item) => (
              <tr key={item.id}>
                <td className="td-strong">{item.name}</td>
                <td className="mono" style={{ textAlign: "right" }}>{currency} {formatMoney(String(item.unit_price))}</td>
                <td><button className="icon-button" aria-label={`Delete ${item.name}`} title="Delete product" onClick={() => void removeProduct(item)}><Trash2 size={14} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
