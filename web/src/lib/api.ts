// Thin client for the Bun API.
import type { FilterState } from "./filters.ts";
import { toSearchParams } from "./filters.ts";

export type EmailRecord = {
  folder_name: string;
  bank: string;
  date: string | null;
  market_wrap: "YES" | "NO";
  primary_asset_tag: string;
  asset_tags: string[];
  companies_mentioned: string[];
  industry_subindustry: string[];
  pdf_attachment: string[] | null;
  source_file: string;
};
export type ListItem = EmailRecord & { snippet: string | null };
export type ListResponse = { total: number; count: number; items: ListItem[] };
export type Facets = Record<"asset" | "bank" | "month" | "industry" | "wrap", Record<string, number>>;
export type Headline = { title: string; url: string; source: string; published_at: string | null };
export type News = { updated_at: string | null; source: string | null; items: Headline[] };

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

export const fetchList = (f: FilterState, signal?: AbortSignal) =>
  get<ListResponse>(`/api/emails?${toSearchParams(f)}`, signal);
export const fetchFacets = (f: FilterState, signal?: AbortSignal) =>
  get<Facets>(`/api/facets?${toSearchParams({ ...f, sort: "new" })}`, signal);
export const fetchEmail = (id: string) => get<EmailRecord>(`/api/emails/${encodeURIComponent(id)}`);
export const fetchNews = () => get<News>("/api/news");

export const emailUrl = (id: string, remote: boolean) =>
  `/raw/${encodeURIComponent(id)}/email.html${remote ? "?remote=1" : ""}`;
export const pdfUrl = (id: string, name: string) =>
  `/raw/${encodeURIComponent(id)}/pdf/${encodeURIComponent(name)}`;
