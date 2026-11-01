// Server side lookup of results/numbers_sheet.json, copied by scripts/build_data.py. A missing key is a build error,
// so a page can never show a number the sheet does not hold.
import sheet from "@/data/numbers.json";

type Row = { value: unknown; unit: string; source: string; stage: string; caveat: number };

const rows = sheet.rows as Record<string, Row>;
const caveatTexts = sheet.caveats as string[];

export const sheetNote = sheet.note as string;
export const sheetEntries = sheet.entries as number;

export function has(key: string): boolean {
  return key in rows;
}

function row(key: string): Row {
  const found = rows[key];
  if (!found) throw new Error(`numbers sheet has no key ${key}`);
  return found;
}

export function num(key: string): number {
  const value = row(key).value;
  if (typeof value !== "number") throw new Error(`numbers sheet key ${key} is not a number`);
  return value;
}

export function str(key: string): string {
  const value = row(key).value;
  if (typeof value !== "string") throw new Error(`numbers sheet key ${key} is not a string`);
  return value;
}

export function bool(key: string): boolean {
  const value = row(key).value;
  if (typeof value !== "boolean") throw new Error(`numbers sheet key ${key} is not a boolean`);
  return value;
}

export function interval(key: string): [number, number] {
  const value = row(key).value;
  if (!Array.isArray(value) || value.length !== 2) throw new Error(`numbers sheet key ${key} is not an interval`);
  return [value[0] as number, value[1] as number];
}

export function any<T>(key: string): T {
  return row(key).value as T;
}

export function sources(keys: string[]): string[] {
  return [...new Set(keys.map((k) => row(k).source))];
}

export function caveats(keys: string[]): string[] {
  return [...new Set(keys.map((k) => caveatTexts[row(k).caveat]))];
}

/** The caveats of every key that starts with one of these prefixes. */
export function caveatsOf(prefixes: string[]): string[] {
  const keys = Object.keys(rows).filter((k) => prefixes.some((p) => k.startsWith(p)));
  return caveats(keys);
}

export function signed(x: number, digits = 2): string {
  const text = Math.abs(x).toFixed(digits);
  if (Number(text) === 0) return text;
  return (x < 0 ? "-" : "+") + text;
}

export function fixed(x: number, digits = 2): string {
  return x.toFixed(digits);
}

export function ciText(ci: [number, number], digits = 2, withSign = true): string {
  const show = withSign ? signed : fixed;
  return `[${show(ci[0], digits)}, ${show(ci[1], digits)}]`;
}

export function usd(x: number, digits = 6): string {
  return `USD ${x.toFixed(digits)}`;
}
