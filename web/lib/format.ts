// Small display helpers that both server and client components can call.

/** Half up, so that 54.05 reads 54.1 and a shown gap equals the difference of the shown numbers. */
export function halfUp(x: number, digits = 1): string {
  const factor = 10 ** digits;
  return (Math.round(x * factor + 1e-6) / factor).toFixed(digits);
}

/** The word joiner keeps "%" and its unit on one visible line. A screen reader has no line to keep, so labels drop it. */
export function spoken(text: string): string {
  return text.replace(/⁠/g, "");
}
