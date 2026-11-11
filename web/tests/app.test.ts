import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createApp } from "../server/app.ts";
import { SAMPLE, fixtureDb } from "./fixture-db.ts";

let dir: string;
let app: ReturnType<typeof createApp>;
const PNG = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2]);

beforeAll(() => {
  dir = mkdtempSync(join(tmpdir(), "dash-"));
  const data = join(dir, "Data");
  mkdirSync(join(data, "001", "inline"), { recursive: true });
  writeFileSync(join(data, "001", "emailbody.html"),
    Buffer.concat([Buffer.from("<html><head></head><body><p>Caf"), Buffer.from([0xe9]),
      Buffer.from("</p><img src='/filestore/x/001/inline/image001'></body></html>")]));
  writeFileSync(join(data, "001", "inline", "image001"), PNG);
  writeFileSync(join(data, "001", "semis.pdf"), "%PDF-1.4 fake");
  writeFileSync(join(data, "001", "secret.txt"), "not listed");
  mkdirSync(join(data, "002"), { recursive: true });
  const dist = join(dir, "dist");
  mkdirSync(join(dist, "assets"), { recursive: true });
  writeFileSync(join(dist, "index.html"), "<!doctype html><title>app</title>");
  writeFileSync(join(dist, "assets", "app.js"), "console.log(1)");
  writeFileSync(join(dir, "news.json"), JSON.stringify({ updated_at: "2026-11-11T10:00:00Z", items: [{ title: "h" }] }));
  app = createApp({ db: fixtureDb(SAMPLE), dataDir: data, distDir: dist, newsPath: join(dir, "news.json") });
});
afterAll(() => rmSync(dir, { recursive: true, force: true }));

const get = (path: string) => app(new Request(`http://localhost:3000${path}`));

describe("api", () => {
  test("list with filters and search", async () => {
    const res = await get("/api/emails?asset=FX&sort=old");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.total).toBe(4);
    expect(body.items.map((i: { source_file: string }) => i.source_file)).toEqual(["003", "004"]);
  });
  test("facets", async () => {
    const body = await (await get("/api/facets?bank=Bank%20A")).json();
    expect(body.bank["Bank B"]).toBe(1);
    expect(body.asset.Equity).toBe(1);
  });
  test("one email, and 404 for unknown ids", async () => {
    expect((await (await get("/api/emails/001")).json()).bank).toBe("Bank A");
    expect((await get("/api/emails/999")).status).toBe(404);
  });
  test("news falls back to an empty feed", async () => {
    expect((await (await get("/api/news")).json()).items).toHaveLength(1);
    const bare = createApp({ db: fixtureDb([]), dataDir: dir });
    expect(await (await bare(new Request("http://x/api/news"))).json()).toEqual({ updated_at: null, source: null, items: [] });
  });
  test("non-GET rejected", async () => {
    expect((await app(new Request("http://localhost/api/emails", { method: "POST" }))).status).toBe(405);
  });
});

describe("raw email files", () => {
  test("email HTML: UTF-8 with replacement, images rewritten, strict CSP", async () => {
    const res = await get("/raw/001/email.html");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Caf�");
    expect(html).toContain('src="inline/image001"');
    expect(res.headers.get("content-type")).toBe("text/html; charset=utf-8");
    const csp = res.headers.get("content-security-policy")!;
    expect(csp).toContain("default-src 'none'");
    expect(csp).not.toContain("https:");
    const remote = await get("/raw/001/email.html?remote=1");
    expect(remote.headers.get("content-security-policy")).toContain("https:");
  });
  test("inline image served with sniffed type", async () => {
    const res = await get("/raw/001/inline/image001");
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("image/png");
  });
  test("listed PDF served inline", async () => {
    const res = await get("/raw/001/pdf/semis.pdf");
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("application/pdf");
    expect(res.headers.get("content-disposition")).toStartWith("inline");
  });
  test.each([
    "/raw/001/pdf/secret.txt",
    "/raw/001/pdf/..%2F..%2Fetc%2Fpasswd",
    "/raw/001/inline/..%2Fsemis.pdf",
    "/raw/001/inline/%2e%2e",
    "/raw/..%2F001/email.html",
    "/raw/999/email.html",
    "/raw/002/email.html",
    "/raw/001/emailbody.html",
    "/raw/001",
    "/raw",
  ])("refuses %s", async (path) => {
    expect((await get(path)).status).toBe(404);
  });
});

describe("static app", () => {
  test("assets and SPA fallback", async () => {
    expect(await (await get("/assets/app.js")).text()).toBe("console.log(1)");
    expect(await (await get("/")).text()).toContain("<title>app</title>");
    expect(await (await get("/some/route")).text()).toContain("<title>app</title>");
  });
  test("no traversal out of dist", async () => {
    const body = await (await get("/../news.json")).text();
    expect(body).toContain("<title>app</title>");
  });
});
