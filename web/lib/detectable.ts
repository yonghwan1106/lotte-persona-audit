// The smallest gap two independent groups can separate, the same arithmetic as results/stage4/detectable.json.
// Checked against that file by scripts/check_detectable.mjs.
export type DetectableParams = { z_alpha: number; z_power: number; p: number };

/** Smallest detectable gap in percentage points with n people per card, one decimal. */
export function smallestGap(n: number, params: DetectableParams): number {
  const raw = (params.z_alpha + params.z_power) * Math.sqrt((2 * params.p * (1 - params.p)) / n) * 100;
  return Math.round(raw * 10) / 10;
}

/** People needed per card to separate a gap in percentage points. */
export function neededPerCard(gapPp: number, params: DetectableParams): number {
  const z = params.z_alpha + params.z_power;
  return Math.ceil((z * z * 2 * params.p * (1 - params.p)) / (gapPp / 100) ** 2);
}
