"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PAGE_SIZE } from "@/components/pagination";

export function usePagedRecords<T>(path: string, filters = "") {
  const [items, setItems] = useState<T[]>([]);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true); setError("");
    try { setItems(await api<T[]>(`${path}?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}${filters}`, {signal})); }
    catch (e) { if (!signal?.aborted) setError(e instanceof Error ? e.message : "Unable to load records"); }
    finally { if (!signal?.aborted) setLoading(false); }
  }, [path, filters, page]);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [load]);
  return {items, setItems, page, setPage, loading, error, setError, load};
}
