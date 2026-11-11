// Filter state: pure functions, mirrored into the URL so a view can be shared.

import { PARENT } from "./taxonomy.ts";
import { monthLabel } from "./format.ts";

export const FACET_KEYS = ["asset", "bank", "month"] as const;
export type FacetKey = (typeof FACET_KEYS)[number];
export type Sort = "new" | "old";
export type FilterState = { q: string; sort: Sort } & Record<FacetKey, string[]>;

export const EMPTY: FilterState = { q: "", sort: "new", asset: [], bank: [], month: [] };

export function toggle(s: FilterState, facet: FacetKey, value: string): FilterState {
  const cur = s[facet];
  return { ...s, [facet]: cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value] };
}

export const clearFacet = (s: FilterState, facet: FacetKey): FilterState => ({ ...s, [facet]: [] });
export const clearAll = (s: FilterState): FilterState => ({ ...EMPTY, sort: s.sort });
export const activeCount = (s: FilterState) => FACET_KEYS.reduce((n, k) => n + s[k].length, 0);

/** Query string for the API and the address bar. Selection extras (id, tab) ride along. */
export function toSearchParams(s: FilterState, extra: Record<string, string | null> = {}): URLSearchParams {
  const p = new URLSearchParams();
  if (s.q.trim()) p.set("q", s.q.trim());
  for (const k of FACET_KEYS) for (const v of s[k]) p.append(k, v);
  if (s.sort !== "new") p.set("sort", s.sort);
  for (const [k, v] of Object.entries(extra)) if (v) p.set(k, v);
  return p;
}

export function fromSearchParams(p: URLSearchParams): FilterState {
  const s: FilterState = { ...EMPTY, q: p.get("q") ?? "", sort: p.get("sort") === "old" ? "old" : "new" };
  for (const k of FACET_KEYS) s[k] = [...new Set(p.getAll(k).filter(Boolean))];
  return s;
}

export type Chip = { facet: FacetKey; value: string; prefix: string; label: string; tag: string | null };

export function chips(s: FilterState): Chip[] {
  const out: Chip[] = [];
  for (const v of s.asset) out.push({ facet: "asset", value: v, prefix: PARENT[v] ? `${PARENT[v]} › ` : "", label: v, tag: v });
  for (const v of s.bank) out.push({ facet: "bank", value: v, prefix: "Bank ", label: v, tag: null });
  for (const v of s.month) out.push({ facet: "month", value: v, prefix: "Date ", label: monthLabel(v), tag: null });
  return out;
}
