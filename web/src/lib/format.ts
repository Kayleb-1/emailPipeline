// Small display helpers.

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const NO_DATE = "none";

export const monthLabel = (key: string) =>
  key === NO_DATE ? "No date" : `${MON[Number(key.slice(5, 7)) - 1]} ${key.slice(0, 4)}`;

export const dateShort = (d: string | null) => (d ? `${d.slice(8, 10)} ${MON[Number(d.slice(5, 7)) - 1]}` : "No date");

export const dateLong = (d: string | null) =>
  d ? `${d.slice(8, 10)} ${MON[Number(d.slice(5, 7)) - 1]} ${d.slice(0, 4)}` : "No date";

/** Months newest first, "No date" last. */
export const sortMonths = (keys: string[]) =>
  [...keys].sort((a, b) => (a === NO_DATE ? 1 : b === NO_DATE ? -1 : b.localeCompare(a)));

export function initials(name: string): string {
  const [first = "", second = ""] = name.match(/[\p{L}\p{N}]+/gu) ?? [];
  if (!first) return "?";
  if (!second) return first.slice(0, 2).toUpperCase();
  return (first.slice(0, 1) + second.slice(0, 1)).toUpperCase();
}

/** Split an FTS snippet into plain and highlighted parts (markers are control chars). */
export function snippetParts(s: string | null): { text: string; hit: boolean }[] {
  if (!s) return [];
  const out: { text: string; hit: boolean }[] = [];
  for (const piece of s.replace(/\s+/g, " ").split("\u0002")) {
    const [hit, rest] = piece.includes("\u0003") ? piece.split("\u0003", 2) : [null, piece];
    if (hit !== null && hit !== "") out.push({ text: hit, hit: true });
    if (rest) out.push({ text: rest, hit: false });
  }
  return out;
}

/** "14:30" in the viewer's time zone. */
export const clock = (iso: string | null) =>
  iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }) : "--:--";

export function splitIndustry(s: string): { sector: string; sub: string } {
  const i = s.indexOf(" > ");
  return i < 0 ? { sector: "INDUSTRY", sub: s } : { sector: s.slice(0, i), sub: s.slice(i + 3) };
}
