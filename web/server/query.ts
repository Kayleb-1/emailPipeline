// Read-only queries over the SQLite index (pipeline/schema.sql).
// Filters combine as OR within a facet and AND across facets. Facet counts for a
// facet ignore that facet's own selection, so every option shows what picking it
// would add.

import type { Database } from "bun:sqlite";

export const FACETS = ["asset", "bank", "month", "industry", "company", "wrap"] as const;
export type Facet = (typeof FACETS)[number];

export type Filters = { q: string; sort: "new" | "old" } & Record<Facet, string[]>;

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

export const NO_DATE = "none";
const MAX_VALUES = 100;

export function parseFilters(params: URLSearchParams): Filters {
  const values = (key: string) =>
    params
      .getAll(key)
      .flatMap((v) => v.split(","))
      .map((v) => v.trim())
      .filter(Boolean)
      .slice(0, MAX_VALUES);
  const f = { q: (params.get("q") ?? "").trim().slice(0, 200), sort: params.get("sort") === "old" ? "old" : "new" } as Filters;
  for (const facet of FACETS) f[facet] = [...new Set(values(facet))];
  return f;
}

/** User text to a safe FTS5 query: every word must match, as a prefix. */
export function ftsQuery(q: string): string | null {
  const words = q.normalize("NFKC").match(/[\p{L}\p{N}]+/gu) ?? [];
  if (!words.length) return null;
  return words.slice(0, 20).map((w) => `"${w}"*`).join(" AND ");
}

type Clause = { sql: string; args: (string | number)[] };

const marks = (n: number) => Array(n).fill("?").join(", ");

function clauses(f: Filters, skip?: Facet): Clause[] {
  const out: Clause[] = [];
  const add = (facet: Facet, build: (vals: string[]) => Clause) => {
    if (facet !== skip && f[facet].length) out.push(build(f[facet]));
  };
  add("asset", (v) => ({
    sql: `e.source_file IN (SELECT source_file FROM email_asset_tags WHERE tag IN (${marks(v.length)}))`,
    args: v,
  }));
  add("bank", (v) => ({ sql: `e.bank IN (${marks(v.length)})`, args: v }));
  add("month", (v) => {
    const months = v.filter((m) => m !== NO_DATE);
    const parts: string[] = [];
    if (months.length) parts.push(`substr(e.date, 1, 7) IN (${marks(months.length)})`);
    if (v.includes(NO_DATE)) parts.push("e.date IS NULL");
    return { sql: `(${parts.join(" OR ")})`, args: months };
  });
  add("industry", (v) => ({
    sql: `e.source_file IN (SELECT source_file FROM email_industries WHERE industry IN (${marks(v.length)}))`,
    args: v,
  }));
  add("company", (v) => ({
    sql: `e.source_file IN (SELECT source_file FROM email_companies WHERE company IN (${marks(v.length)}))`,
    args: v,
  }));
  add("wrap", (v) => ({ sql: `e.market_wrap IN (${marks(v.length)})`, args: v }));
  const match = ftsQuery(f.q);
  if (match) {
    out.push({
      sql: "e.source_file IN (SELECT source_file FROM email_fts WHERE email_fts MATCH ?)",
      args: [match],
    });
  }
  return out;
}

function where(cs: Clause[]): { sql: string; args: (string | number)[] } {
  if (!cs.length) return { sql: "", args: [] };
  return { sql: "WHERE " + cs.map((c) => c.sql).join(" AND "), args: cs.flatMap((c) => c.args) };
}

// Snippet highlight markers: control characters, so email text can't fake them.
export const MARK_START = "\u0002";
export const MARK_END = "\u0003";

export function listEmails(db: Database, f: Filters): { total: number; count: number; items: ListItem[] } {
  const total = (db.query("SELECT count(*) AS n FROM emails").get() as { n: number }).n;
  const w = where(clauses(f));
  const order = f.sort === "old" ? "e.date IS NULL, e.date ASC" : "e.date IS NULL, e.date DESC";
  const rows = db
    .query(`SELECT e.record_json AS json FROM emails e ${w.sql} ORDER BY ${order}, e.source_file`)
    .all(...w.args) as { json: string }[];
  const items: ListItem[] = rows.map((r) => ({ ...(JSON.parse(r.json) as EmailRecord), snippet: null }));

  const match = ftsQuery(f.q);
  if (match && items.length) {
    const snippets = db
      .query(
        `SELECT source_file, snippet(email_fts, -1, '${MARK_START}', '${MARK_END}', '…', 14) AS s
         FROM email_fts WHERE email_fts MATCH ?`,
      )
      .all(match) as { source_file: string; s: string }[];
    const bySource = new Map(snippets.map((r) => [r.source_file, r.s]));
    for (const item of items) item.snippet = bySource.get(item.source_file) ?? null;
  }
  return { total, count: items.length, items };
}

export type FacetCounts = Record<"asset" | "bank" | "month" | "industry" | "wrap", Record<string, number>>;

export function facetCounts(db: Database, f: Filters): FacetCounts {
  const count = (facet: Facet, select: string, from: string, domain: string): Record<string, number> => {
    const out: Record<string, number> = {};
    for (const r of db.query(domain).all() as { v: string }[]) out[r.v] = 0;
    const w = where(clauses(f, facet));
    const rows = db
      .query(`SELECT ${select} AS v, count(DISTINCT e.source_file) AS n FROM emails e ${from} ${w.sql} GROUP BY v`)
      .all(...w.args) as { v: string; n: number }[];
    for (const r of rows) out[r.v] = r.n;
    return out;
  };
  const monthExpr = `coalesce(substr(e.date, 1, 7), '${NO_DATE}')`;
  return {
    asset: count("asset", "t.tag", "JOIN email_asset_tags t ON t.source_file = e.source_file",
      "SELECT DISTINCT tag AS v FROM email_asset_tags"),
    bank: count("bank", "e.bank", "", "SELECT DISTINCT bank AS v FROM emails"),
    month: count("month", monthExpr, "", `SELECT DISTINCT ${monthExpr} AS v FROM emails e`),
    industry: count("industry", "i.industry", "JOIN email_industries i ON i.source_file = e.source_file",
      "SELECT DISTINCT industry AS v FROM email_industries"),
    wrap: count("wrap", "e.market_wrap", "", "SELECT DISTINCT market_wrap AS v FROM emails"),
  };
}

export function getEmail(db: Database, sourceFile: string): EmailRecord | null {
  const row = db.query("SELECT record_json AS json FROM emails WHERE source_file = ?").get(sourceFile) as
    | { json: string }
    | null;
  return row ? (JSON.parse(row.json) as EmailRecord) : null;
}

export function meta(db: Database): Record<string, string> {
  const rows = db.query("SELECT key, value FROM meta").all() as { key: string; value: string }[];
  return Object.fromEntries(rows.map((r) => [r.key, r.value]));
}
