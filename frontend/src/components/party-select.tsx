"use client";
import { useEffect, useId, useState } from "react";
import { api, Party } from "@/lib/api";

export function PartySelect({kind, name, label, defaultId = ""}: {kind: "customers" | "suppliers"; name: string; label: string; defaultId?: string}) {
  const id = useId();
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<Party[]>([]);
  const [selected, setSelected] = useState<Party | null>(null);
  const [value, setValue] = useState(defaultId);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api<Party[]>(`/${kind}?limit=50&q=${encodeURIComponent(query)}`, {signal: controller.signal}).then(rows => {setItems(rows); setError("");}).catch(e => {if (!controller.signal.aborted) setError(e.message);});
    }, 150);
    return () => {clearTimeout(timer); controller.abort();};
  }, [kind, query, retry]);
  useEffect(() => { if (defaultId) api<Party>(`/${kind}/${defaultId}`).then(setSelected).catch(e => setError(e.message)); }, [kind, defaultId]);
  const options = selected && !items.some(item => item.id === selected.id) ? [selected, ...items] : items;
  return <div className="field"><label htmlFor={id}>{label}</label><input className="search" aria-label={`Search ${kind}`} value={query} placeholder={`Search ${kind}…`} maxLength={200} onChange={e => setQuery(e.target.value)}/><select id={id} name={name} value={value} required onChange={e => {setValue(e.target.value); setSelected(options.find(item => item.id === e.target.value) ?? null);}}><option value="" disabled>Select {label.toLowerCase()}</option>{options.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>{error && <p className="error-text" role="alert">{error} <button className="button" type="button" onClick={() => setRetry(current => current + 1)}>Retry options</button></p>}</div>;
}
