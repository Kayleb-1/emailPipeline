// HTTP routes for the dashboard. A plain fetch handler, so tests call it directly.
//
//   GET /api/emails?q&asset&bank&month&industry&company&wrap&sort   list + snippets
//   GET /api/facets?...same filters                                 counts per facet value
//   GET /api/emails/:id                                             one record
//   GET /api/meta                                                   index build info
//   GET /api/news                                                   news.json (ticker)
//   GET /raw/:id/email.html[?remote=1]                              email HTML for the sandboxed iframe
//   GET /raw/:id/inline/:file                                       inline image
//   GET /raw/:id/pdf/:file                                          PDF attachment
//   anything else                                                   the built Svelte app (dist/)

import type { Database } from "bun:sqlite";
import { existsSync } from "node:fs";
import { join, normalize } from "node:path";
import { facetCounts, getEmail, listEmails, meta, parseFilters } from "./query.ts";
import { emailCsp, findHtml, listInline, loadHtml, rewriteEmailHtml, sniffImageType } from "./raw.ts";

export type AppConfig = {
  db: Database;
  dataDir: string;
  distDir?: string;
  newsPath?: string;
};

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });

const notFound = (what = "not found") => json({ error: what }, 404);

export function createApp(cfg: AppConfig) {
  return async function fetch(req: Request): Promise<Response> {
    const url = new URL(req.url);
    if (req.method !== "GET" && req.method !== "HEAD") return json({ error: "method not allowed" }, 405);
    const parts = url.pathname.split("/").filter(Boolean).map((p) => {
      try {
        return decodeURIComponent(p);
      } catch {
        return "\0";
      }
    });

    if (parts[0] === "api") {
      if (parts[1] === "emails" && parts.length === 2) return json(listEmails(cfg.db, parseFilters(url.searchParams)));
      if (parts[1] === "emails" && parts.length === 3) {
        const record = getEmail(cfg.db, parts[2]);
        return record ? json(record) : notFound("unknown email");
      }
      if (parts[1] === "facets" && parts.length === 2) return json(facetCounts(cfg.db, parseFilters(url.searchParams)));
      if (parts[1] === "meta" && parts.length === 2) return json(meta(cfg.db));
      if (parts[1] === "news" && parts.length === 2) return news(cfg.newsPath);
      return notFound();
    }

    if (parts[0] === "raw") {
      if (parts.length < 3) return notFound();
      const record = getEmail(cfg.db, parts[1]);
      if (!record) return notFound("unknown email");
      const id = record.source_file;

      if (parts[2] === "email.html" && parts.length === 3) {
        const path = findHtml(cfg.dataDir, id);
        if (!path) return notFound("no emailbody.html");
        const html = rewriteEmailHtml(await loadHtml(path), listInline(cfg.dataDir, id));
        return new Response(html, {
          headers: {
            "content-type": "text/html; charset=utf-8",
            "content-security-policy": emailCsp(url.origin, url.searchParams.get("remote") === "1"),
            "x-content-type-options": "nosniff",
            "referrer-policy": "no-referrer",
          },
        });
      }
      if (parts[2] === "inline" && parts.length === 4) {
        const name = listInline(cfg.dataDir, id).find((n) => n === parts[3]);
        if (!name) return notFound("unknown image");
        const file = Bun.file(join(cfg.dataDir, id, "inline", name));
        const type = sniffImageType(new Uint8Array(await file.slice(0, 16).arrayBuffer()));
        return new Response(file, { headers: { "content-type": type, "x-content-type-options": "nosniff" } });
      }
      if (parts[2] === "pdf" && parts.length === 4) {
        const name = (record.pdf_attachment ?? []).find((n) => n === parts[3]);
        const path = name && join(cfg.dataDir, id, name);
        if (!path || !existsSync(path)) return notFound("unknown PDF");
        return new Response(Bun.file(path), {
          headers: {
            "content-type": "application/pdf",
            "content-disposition": `inline; filename*=UTF-8''${encodeURIComponent(name)}`,
            "x-content-type-options": "nosniff",
          },
        });
      }
      return notFound();
    }

    return staticFile(cfg.distDir, url.pathname);
  };
}

async function news(path?: string): Promise<Response> {
  if (path && existsSync(path)) {
    try {
      return json(JSON.parse(await Bun.file(path).text()));
    } catch {}
  }
  return json({ updated_at: null, source: null, items: [] });
}

async function staticFile(distDir: string | undefined, pathname: string): Promise<Response> {
  if (!distDir || !existsSync(distDir)) {
    return new Response("Dashboard not built. Run `bun run build`, or use `bun run dev`.", { status: 404 });
  }
  const rel = normalize(pathname).replace(/^(\.\.[/\\])+/, "");
  const candidate = join(distDir, rel);
  if (candidate.startsWith(distDir) && rel !== "/" && existsSync(candidate) && Bun.file(candidate).size > 0) {
    return new Response(Bun.file(candidate));
  }
  return new Response(Bun.file(join(distDir, "index.html")), { headers: { "content-type": "text/html; charset=utf-8" } });
}
