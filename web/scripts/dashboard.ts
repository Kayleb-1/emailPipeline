// One command to see the project: install, index (only when stale), build, serve.
//
//   bun run dashboard                  uses ./Data next to the repo
//   bun run dashboard --data <path>    or a dataset elsewhere (also DATA_DIR)
//   bun run dashboard --port 3001
//
// Needs Bun and uv; uv brings Python and the pinned packages on first use.

import { Database } from "bun:sqlite";
import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

const web = resolve(import.meta.dir, "..");
const repo = resolve(web, "..");

export function arg(argv: string[], name: string): string | undefined {
  const i = argv.indexOf(`--${name}`);
  if (i >= 0) return argv[i + 1];
  return argv.find((a) => a.startsWith(`--${name}=`))?.split("=").slice(1).join("=");
}

/** The index needs rebuilding when it's missing, or built from another JSON or data folder. */
export function indexIsStale(dbPath: string, jsonPath: string, dataDir: string): boolean {
  if (!existsSync(dbPath)) return true;
  try {
    const db = new Database(dbPath, { readonly: true });
    const rows = db.query("SELECT key, value FROM meta").all() as { key: string; value: string }[];
    db.close();
    const meta = Object.fromEntries(rows.map((r) => [r.key, r.value]));
    const sha = new Bun.CryptoHasher("sha256").update(readFileSync(jsonPath)).digest("hex");
    return meta.source_sha256 !== sha || resolve(meta.data_dir ?? "") !== resolve(dataDir);
  } catch {
    return true;
  }
}

function step(label: string, cmd: string[], cwd: string): void {
  console.log(`\n> ${label}`);
  const res = Bun.spawnSync(cmd, { cwd, stdio: ["inherit", "inherit", "inherit"] });
  if (res.exitCode !== 0) {
    console.error(`\n${label} failed (exit ${res.exitCode}).`);
    process.exit(res.exitCode ?? 1);
  }
}

if (import.meta.main) {
  const argv = process.argv.slice(2);
  const dataDir = resolve(repo, arg(argv, "data") ?? process.env.DATA_DIR ?? "Data");
  const port = arg(argv, "port") ?? process.env.PORT ?? "3000";
  const json = join(repo, "classified_emails.json");
  const db = join(web, "data", "emails.db");

  if (!existsSync(dataDir)) {
    console.error(`Data folder not found: ${dataDir}\nPut the dataset at ./Data or pass --data <path>.`);
    process.exit(1);
  }
  step("Installing dashboard packages", ["bun", "install", "--frozen-lockfile"], web);
  if (indexIsStale(db, json, dataDir)) {
    step("Building the search index", ["uv", "run", "python", "build_index.py", "--json", json, "--data", dataDir, "--out", db], repo);
  } else {
    console.log("\n> Search index is up to date");
  }
  step("Building the dashboard", ["bun", "run", "build"], web);
  console.log(`\n> Starting on http://127.0.0.1:${port}  (Ctrl+C to stop)\n`);
  const server = Bun.spawn(["bun", "run", "server/index.ts"], {
    cwd: web, env: { ...process.env, PORT: port, DATA_DIR: dataDir }, stdio: ["inherit", "inherit", "inherit"],
  });
  process.exit(await server.exited);
}
