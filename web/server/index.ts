// Starts the dashboard server.
//
//   bun run start            serve the built app (dist/) plus the API on PORT (default 3000)
//   bun run dev              API only; Vite serves the app and proxies /api and /raw here
//
// Environment: DB_PATH (default data/emails.db), DATA_DIR (default: the folder the
// index was built from), NEWS_PATH (default data/news.json), PORT.

import { Database } from "bun:sqlite";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { createApp } from "./app.ts";
import { meta } from "./query.ts";

const root = resolve(import.meta.dir, "..");
const dbPath = resolve(process.env.DB_PATH ?? join(root, "data", "emails.db"));
if (!existsSync(dbPath)) {
  console.error(`No index at ${dbPath}. Build it first:\n  uv run python build_index.py --json classified_emails.json --data <Data folder>`);
  process.exit(1);
}
const db = new Database(dbPath, { readonly: true });
const dataDir = resolve(process.env.DATA_DIR ?? meta(db).data_dir ?? "Data");
if (!existsSync(dataDir)) console.warn(`Warning: data folder ${dataDir} not found; email bodies won't render.`);

const dev = process.argv.includes("--dev");
const port = Number(process.env.PORT ?? (dev ? 3001 : 3000));
const app = createApp({
  db,
  dataDir,
  distDir: dev ? undefined : join(root, "dist"),
  newsPath: resolve(process.env.NEWS_PATH ?? join(root, "data", "news.json")),
});

const server = Bun.serve({ port, hostname: "127.0.0.1", fetch: app });
console.log(`Dashboard ${dev ? "API" : ""} on http://${server.hostname}:${server.port}  (index: ${dbPath}, data: ${dataDir})`);
