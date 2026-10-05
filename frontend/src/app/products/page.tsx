"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api, Organization, Product } from "@/lib/api";

export default function Products() {
  const [items, setItems] = useState<Product[]>([]);
  const [currency, setCurrency] = useState("DKK");
  const [name, setName] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      const [products, orgs] = await Promise.all([
        api<Product[]>("/products"),
        api<Organization[]>("/organizations"),
      ]);
      setItems(products);
      if (orgs[0]?.currency) setCurrency(orgs[0].currency);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load products");
    }
  }

  useEffect(() => { void load(); }, []);

  async function createProduct(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const item = await api<Product>("/products", {
        method: "POST",
        body: JSON.stringify({ name, unit_price: unitPrice.replace(",", ".") }),
      });
      setItems((current) => [...current, item].sort((a, b) => a.name.localeCompare(b.name)));
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
      setItems((current) => current.filter((product) => product.id !== item.id));
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
          <button className="button button-primary" disabled={saving}><Plus size={14} />{saving ? "Saving…" : "Add product"}</button>
        </div>
      </form>

      {error && <p className="error-text" role="alert">{error}</p>}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Product or service</th><th style={{ textAlign: "right" }}>Unit price</th><th style={{ width: 48 }} /></tr></thead>
          <tbody>
            {items.length === 0 ? (
              <tr><td colSpan={3} className="empty">No saved products yet. Add one above to use it on invoices.</td></tr>
            ) : items.map((item) => (
              <tr key={item.id}>
                <td className="td-strong">{item.name}</td>
                <td className="mono" style={{ textAlign: "right" }}>{currency} {Number(item.unit_price).toLocaleString("en-DK", { minimumFractionDigits: 2 })}</td>
                <td><button className="icon-button" aria-label={`Delete ${item.name}`} title="Delete product" onClick={() => void removeProduct(item)}><Trash2 size={14} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
