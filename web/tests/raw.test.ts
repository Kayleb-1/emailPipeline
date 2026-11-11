import { describe, expect, test } from "bun:test";
import { candidateName, emailCsp, resolveInline, rewriteEmailHtml, sniffImageType } from "../server/raw.ts";

const NAMES = ["image001.png", "Chart 2.JPG", "inline-cid-abc", "logo.gif"];

describe("resolveInline", () => {
  test("absolute server path, relative path and cid", () => {
    expect(resolveInline("/filestore/market_research/035242/inline/image001.png", NAMES)).toBe("image001.png");
    expect(resolveInline("inline/chart%202.jpg", NAMES)).toBe("Chart 2.JPG");
    expect(resolveInline("cid:logo.gif@01DC.1234", NAMES)).toBe("logo.gif");
    expect(resolveInline("cid:logo@x", NAMES)).toBe("logo.gif");
    expect(resolveInline("cid:inline-cid-abc", NAMES)).toBe("inline-cid-abc");
  });
  test("remote, data and unknown references are left alone", () => {
    expect(resolveInline("https://bank.example.com/image001.png", NAMES)).toBeNull();
    expect(resolveInline("//cdn.example.com/logo.gif", NAMES)).toBeNull();
    expect(resolveInline("data:image/png;base64,AAAA", NAMES)).toBeNull();
    expect(resolveInline("inline/missing.png", NAMES)).toBeNull();
    expect(resolveInline("", NAMES)).toBeNull();
  });
  test("traversal in a reference can only ever pick a listed name", () => {
    expect(candidateName("../../etc/passwd")).toBe("passwd");
    expect(resolveInline("../../etc/passwd", NAMES)).toBeNull();
  });
});

describe("rewriteEmailHtml", () => {
  test("rewrites img src in any quoting, backgrounds and CSS url()", () => {
    const html = `<html><head><title>x</title></head><body>
      <img src='/filestore/x/inline/image001.png'>
      <img src="cid:logo.gif@abc" alt="logo">
      <img src=inline/Chart%202.JPG>
      <td background="inline/image001.png"></td>
      <div style="background-image: url('cid:inline-cid-abc')"></div>
      <img src="https://tracker.example.com/p.gif"></body></html>`;
    const out = rewriteEmailHtml(html, NAMES);
    expect(out).toContain(`src="inline/image001.png"`);
    expect(out).toContain(`src="inline/logo.gif"`);
    expect(out).toContain(`src="inline/Chart%202.JPG"`);
    expect(out).toContain(`background="inline/image001.png"`);
    expect(out).toContain(`url('inline/inline-cid-abc')`);
    expect(out).toContain(`src="https://tracker.example.com/p.gif"`);
  });
  test("adds a base target so links open in a new tab", () => {
    expect(rewriteEmailHtml("<html><head></head><body></body></html>", [])).toContain('<head><base target="_blank">');
    expect(rewriteEmailHtml("<html><body>x</body></html>", [])).toContain('<html><head><base target="_blank"></head>');
    expect(rewriteEmailHtml("<p>x</p>", [])).toBe('<base target="_blank"><p>x</p>');
  });
});

describe("emailCsp", () => {
  test("blocks scripts and remote images by default", () => {
    const csp = emailCsp("http://localhost:3000", false);
    expect(csp).toContain("default-src 'none'");
    expect(csp).toContain("img-src http://localhost:3000 data:");
    expect(csp).not.toContain("script-src");
    expect(csp).not.toContain("https:");
  });
  test("remote images on request", () => {
    expect(emailCsp("http://localhost:3000", true)).toContain("img-src http://localhost:3000 data: https: http:");
  });
});

test("sniffImageType", () => {
  expect(sniffImageType(new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d]))).toBe("image/png");
  expect(sniffImageType(new Uint8Array([0xff, 0xd8, 0xff, 0xe0]))).toBe("image/jpeg");
  expect(sniffImageType(new TextEncoder().encode("GIF89a"))).toBe("image/gif");
  expect(sniffImageType(new TextEncoder().encode("RIFF0000WEBPVP8"))).toBe("image/webp");
  expect(sniffImageType(new Uint8Array([1, 2, 3]))).toBe("application/octet-stream");
});
