// In-memory index built from the shared schema, filled the way index_db.py fills it.
import { Database } from "bun:sqlite";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { EmailRecord } from "../server/query.ts";

const SCHEMA = readFileSync(join(import.meta.dir, "../../pipeline/schema.sql"), "utf8");
const PARENT: Record<string, string> = {
  "Developed Markets": "Macro", "Emerging Markets": "Macro",
  "Credit Strategy": "Fixed Income", "Rates Strategy": "Fixed Income", Securitisation: "Fixed Income",
  "Company Research": "Equity", "Portfolio Strategy": "Equity", "Thematic Investing": "Equity",
  Energy: "Commodities", Metals: "Commodities", Agriculture: "Commodities",
  USD: "FX", EUR: "FX", JPY: "FX", GBP: "FX", CHF: "FX", Other: "FX",
};

export function record(over: Partial<EmailRecord> & { source_file: string }): EmailRecord {
  return {
    folder_name: "Note", bank: "Bank A", date: "2026-04-09", market_wrap: "NO",
    primary_asset_tag: "Macro", asset_tags: ["Macro"], companies_mentioned: [],
    industry_subindustry: [], pdf_attachment: null, ...over,
  };
}

export function fixtureDb(rows: { r: EmailRecord; body?: string; pdf?: string }[]): Database {
  const db = new Database(":memory:");
  db.exec(SCHEMA);
  for (const { r, body = "", pdf = "" } of rows) {
    db.query("INSERT INTO emails VALUES (?, ?, ?, ?, ?, ?, ?, ?)").run(
      r.source_file, r.folder_name, r.bank, r.date, r.market_wrap, r.primary_asset_tag,
      r.pdf_attachment ? 1 : 0, JSON.stringify(r),
    );
    for (const t of r.asset_tags)
      db.query("INSERT INTO email_asset_tags VALUES (?, ?, ?, ?)").run(
        r.source_file, t, PARENT[t] ?? null, t === r.primary_asset_tag ? 1 : 0);
    for (const c of r.companies_mentioned)
      db.query("INSERT INTO email_companies VALUES (?, ?)").run(r.source_file, c);
    for (const i of r.industry_subindustry)
      db.query("INSERT INTO email_industries VALUES (?, ?, ?)").run(
        r.source_file, i, i.includes(" > ") ? i.split(" > ")[0] : null);
    (r.pdf_attachment ?? []).forEach((p, i) =>
      db.query("INSERT INTO email_pdfs VALUES (?, ?, ?)").run(r.source_file, p, i));
    db.query("INSERT INTO email_fts VALUES (?, ?, ?, ?, ?, ?, ?)").run(
      r.source_file, r.folder_name, r.bank, r.companies_mentioned.join("; "),
      r.industry_subindustry.join("; "), body, pdf);
  }
  db.query("INSERT INTO meta VALUES ('records', ?)").run(String(rows.length));
  return db;
}

export const SAMPLE = [
  {
    r: record({ source_file: "001", folder_name: "Semis: raising estimates", bank: "Bank A", date: "2026-04-09",
      primary_asset_tag: "Equity", asset_tags: ["Equity", "Company Research"],
      companies_mentioned: ["Company Alpha"], industry_subindustry: ["TECHNOLOGY > Semiconductors"],
      pdf_attachment: ["semis.pdf"] }),
    body: "Our zygomorphic thesis on wafer demand.", pdf: "Quokka supply checks",
  },
  {
    r: record({ source_file: "002", folder_name: "Morning Market Wrap", bank: "Bank B", date: "2026-04-10",
      market_wrap: "YES", primary_asset_tag: "Market Wrap", asset_tags: ["Market Wrap"] }),
    body: "Equities fell, yields rose, café owners worried.",
  },
  {
    r: record({ source_file: "003", folder_name: "FX Weekly: USD and JPY", bank: "Bank A", date: "2026-03-30",
      primary_asset_tag: "FX", asset_tags: ["FX", "USD", "JPY"] }),
    body: "Intervention risk in the yen.",
  },
  {
    r: record({ source_file: "004", folder_name: "Rates outlook", bank: "Bank C", date: null,
      primary_asset_tag: "Fixed Income", asset_tags: ["Fixed Income", "Rates Strategy", "FX", "USD"] }),
    body: "Curve steepening into year end.",
  },
];
