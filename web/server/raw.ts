// Serving an email's own files: its HTML (for the sandboxed viewer), inline images and PDFs.
//
// Only names that exist on disk are ever served: the email id must be in the index,
// an inline image must be a file in that email's inline/ folder, and a PDF must be
// listed in the record's pdf_attachment. Paths are never built from raw input.

import { existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

/** The file name a reference points at (same rule as pipeline/images.py). */
export function candidateName(ref: string): string {
  if (/^cid:/i.test(ref)) return safeDecode(ref.slice(4)).split("@")[0];
  let path = ref;
  try {
    path = new URL(ref, "http://x/").pathname;
  } catch {}
  return safeDecode(path).replace(/\\/g, "/").replace(/\/+$/, "").split("/").pop() ?? "";
}

function safeDecode(s: string): string {
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

const isExternal = (ref: string) => /^(https?:|data:|\/\/)/i.test(ref.trim());

/** Map a reference to a file in inline/, or null. Case-insensitive, cid without extension allowed. */
export function resolveInline(ref: string, inlineNames: string[]): string | null {
  if (!ref || isExternal(ref)) return null;
  const want = candidateName(ref.trim()).toLowerCase();
  if (!want) return null;
  const exact = inlineNames.find((n) => n.toLowerCase() === want);
  if (exact) return exact;
  if (/^cid:/i.test(ref.trim())) return inlineNames.find((n) => n.toLowerCase().replace(/\.[^.]+$/, "") === want) ?? null;
  return null;
}

const escapeAttr = (s: string) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;");

/**
 * Point image references at inline/<file> (served next to the HTML) and open links
 * in a new tab. Everything else in the email is left as it is.
 */
export function rewriteEmailHtml(html: string, inlineNames: string[]): string {
  const local = (ref: string) => {
    const name = resolveInline(ref, inlineNames);
    return name ? `inline/${encodeURIComponent(name)}` : null;
  };
  let out = html.replace(
    /(\s(?:src|background)\s*=\s*)(?:"([^"]*)"|'([^']*)'|([^\s>]+))/gi,
    (m, pre: string, dq?: string, sq?: string, bare?: string) => {
      const target = local((dq ?? sq ?? bare ?? "").replace(/&amp;/g, "&"));
      return target ? `${pre}"${escapeAttr(target)}"` : m;
    },
  );
  out = out.replace(/url\(\s*(['"]?)([^'")]+)\1\s*\)/gi, (m, _q: string, ref: string) => {
    const target = local(ref.replace(/&amp;/g, "&"));
    return target ? `url('${target}')` : m;
  });
  const base = '<base target="_blank">';
  if (/<head[^>]*>/i.test(out)) return out.replace(/<head[^>]*>/i, (h) => h + base);
  if (/<html[^>]*>/i.test(out)) return out.replace(/<html[^>]*>/i, (h) => `${h}<head>${base}</head>`);
  return base + out;
}

/**
 * CSP for the email document: no scripts, no forms, no frames. Images from this
 * server only, unless the reader asked for remote images (tracking pixels otherwise
 * report the open to the sender).
 */
export function emailCsp(origin: string, remoteImages: boolean): string {
  const img = remoteImages ? `${origin} data: https: http:` : `${origin} data:`;
  return [
    "default-src 'none'",
    `img-src ${img}`,
    "style-src 'unsafe-inline'",
    `font-src ${remoteImages ? "data: https:" : "data:"}`,
    "form-action 'none'",
    "frame-ancestors 'self'",
    "base-uri 'none'",
  ].join("; ");
}

export function listInline(dataDir: string, sourceFile: string): string[] {
  const dir = join(dataDir, sourceFile, "inline");
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((n) => statSync(join(dir, n)).isFile());
}

export function findHtml(dataDir: string, sourceFile: string): string | null {
  const dir = join(dataDir, sourceFile);
  if (!existsSync(dir)) return null;
  const name = readdirSync(dir).find((n) => n.toLowerCase() === "emailbody.html");
  return name ? join(dir, name) : null;
}

/** Always decoded as UTF-8 with bad bytes replaced, like the pipeline. */
export async function loadHtml(path: string): Promise<string> {
  return new TextDecoder("utf-8").decode(await Bun.file(path).arrayBuffer());
}

const MEDIA: [Uint8Array, string][] = [
  [new Uint8Array([0x89, 0x50, 0x4e, 0x47]), "image/png"],
  [new Uint8Array([0xff, 0xd8, 0xff]), "image/jpeg"],
  [new TextEncoder().encode("GIF8"), "image/gif"],
];

/** Image type from the bytes; some inline files have no extension. */
export function sniffImageType(bytes: Uint8Array): string {
  for (const [magic, type] of MEDIA) if (magic.every((b, i) => bytes[i] === b)) return type;
  const head = new TextDecoder().decode(bytes.slice(0, 12));
  if (head.startsWith("RIFF") && head.slice(8, 12) === "WEBP") return "image/webp";
  return "application/octet-stream";
}
