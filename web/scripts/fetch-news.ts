// Fetch live financial headlines from free RSS/Atom feeds into data/news.json.
//
//   bun run news             fetch once
//   bun run news --watch     fetch now and every 10 minutes
//
// The dashboard server also runs the 10-minute loop itself (see server/index.ts).
// A failed refresh never replaces good headlines with an empty file.

import { mkdirSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

export type Headline = { title: string; url: string; source: string; published_at: string | null };
export type News = { updated_at: string; source: string; items: Headline[] };

export const FEEDS = [
  { name: "CNBC", url: "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114" },
  { name: "MarketWatch", url: "https://feeds.content.dowjones.io/public/rss/mw_topstories" },
  { name: "Yahoo Finance", url: "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US" },
  { name: "FT Markets", url: "https://www.ft.com/markets?format=rss" },
];
export const REFRESH_MS = 10 * 60 * 1000;
export const MAX_ITEMS = 40;

const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

export function decodeEntities(s: string): string {
  return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e: string) => {
    if (e[0] === "#") {
      const code = e[1].toLowerCase() === "x" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      return Number.isFinite(code) && code > 0 && code < 0x110000 ? String.fromCodePoint(code) : m;
    }
    return ENTITIES[e.toLowerCase()] ?? m;
  });
}

function text(block: string, tag: string): string | null {
  const m = block.match(new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)</${tag}>`, "i"));
  if (!m) return null;
  const raw = m[1].replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1");
  return decodeEntities(raw.replace(/<[^>]+>/g, "")).replace(/\s+/g, " ").trim() || null;
}

function safeUrl(u: string | null): string | null {
  if (!u) return null;
  try {
    const url = new URL(u.trim());
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
}

function isoDate(s: string | null): string | null {
  if (!s) return null;
  const t = Date.parse(s);
  return Number.isNaN(t) ? null : new Date(t).toISOString();
}

/** Headlines from an RSS 2.0 or Atom document. */
export function parseFeed(xml: string, source: string): Headline[] {
  const out: Headline[] = [];
  for (const [, block] of xml.matchAll(/<item\b[^>]*>([\s\S]*?)<\/item>/gi)) {
    const url = safeUrl(text(block, "link") ?? text(block, "guid"));
    const title = text(block, "title");
    if (title && url) out.push({ title, url, source, published_at: isoDate(text(block, "pubDate") ?? text(block, "dc:date")) });
  }
  for (const [, block] of xml.matchAll(/<entry\b[^>]*>([\s\S]*?)<\/entry>/gi)) {
    const href = block.match(/<link\b[^>]*?href=["']([^"']+)["'][^>]*>/i)?.[1] ?? null;
    const url = safeUrl(href && decodeEntities(href));
    const title = text(block, "title");
    if (title && url) out.push({ title, url, source, published_at: isoDate(text(block, "updated") ?? text(block, "published")) });
  }
  return out;
}

/** Newest first, one per title, at most `limit`. */
export function mergeHeadlines(lists: Headline[][], limit = MAX_ITEMS): Headline[] {
  const seen = new Set<string>();
  const all = lists.flat().filter((h) => {
    const key = h.title.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  all.sort((a, b) => (b.published_at ?? "").localeCompare(a.published_at ?? ""));
  return all.slice(0, limit);
}

type Fetch = (url: string, init?: RequestInit) => Promise<Response>;

export async function fetchNews(feeds = FEEDS, fetchImpl: Fetch = fetch, now = new Date()): Promise<{ news: News; errors: string[] }> {
  const errors: string[] = [];
  const results = await Promise.all(
    feeds.map(async (f) => {
      try {
        const res = await fetchImpl(f.url, {
          headers: { "user-agent": "research-dashboard/1.0 (+rss reader)", accept: "application/rss+xml, application/atom+xml, application/xml, text/xml" },
          signal: AbortSignal.timeout(15_000),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const items = parseFeed(await res.text(), f.name);
        if (!items.length) throw new Error("no headlines in feed");
        return items;
      } catch (e) {
        errors.push(`${f.name}: ${(e as Error).message}`);
        return [];
      }
    }),
  );
  const ok = feeds.filter((_, i) => results[i].length).map((f) => f.name);
  return {
    news: { updated_at: now.toISOString(), source: ok.join(", "), items: mergeHeadlines(results) },
    errors,
  };
}

export function writeNews(path: string, news: News): void {
  mkdirSync(dirname(path), { recursive: true });
  const tmp = `${path}.${process.pid}.tmp`;
  writeFileSync(tmp, JSON.stringify(news, null, 2) + "\n");
  renameSync(tmp, path);
}

/** Fetch and save; keeps the previous file when every feed failed. */
export async function refresh(path: string, fetchImpl: Fetch = fetch): Promise<boolean> {
  const { news, errors } = await fetchNews(FEEDS, fetchImpl);
  for (const e of errors) console.warn(`news: ${e}`);
  if (!news.items.length) {
    console.warn("news: no headlines fetched, keeping the previous file");
    return false;
  }
  writeNews(path, news);
  console.log(`news: ${news.items.length} headlines from ${news.source} at ${news.updated_at}`);
  return true;
}

export function startNewsLoop(path: string, everyMs = REFRESH_MS): () => void {
  refresh(path).catch((e) => console.warn(`news: ${e}`));
  const timer = setInterval(() => refresh(path).catch((e) => console.warn(`news: ${e}`)), everyMs);
  return () => clearInterval(timer);
}

if (import.meta.main) {
  const path = resolve(process.env.NEWS_PATH ?? join(import.meta.dir, "..", "data", "news.json"));
  if (process.argv.includes("--watch")) startNewsLoop(path);
  else process.exit((await refresh(path)) ? 0 : 1);
}
