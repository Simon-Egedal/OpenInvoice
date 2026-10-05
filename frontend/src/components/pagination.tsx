"use client";
export const PAGE_SIZE = 50;
export function Pagination({page, count, busy, onPage}: {page: number; count: number; busy: boolean; onPage: (page: number) => void}) {
  return <nav className="row-actions" aria-label="Pagination"><button className="button" disabled={busy || page === 0} onClick={() => onPage(page - 1)}>Previous</button><span>Page {page + 1}</span><button className="button" disabled={busy || count < PAGE_SIZE} onClick={() => onPage(page + 1)}>Next</button></nav>;
}
