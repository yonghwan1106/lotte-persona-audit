// In-memory daily caps for the intake route. Per server process: a restart clears them, and several instances would each
// keep their own count. The numbers are shown in the UI. Only a call that reaches the model counts.

export const CAPS = {
  perIpDaily: positiveInt(process.env.INTAKE_PER_IP_DAILY, 5),
  globalDaily: positiveInt(process.env.INTAKE_GLOBAL_DAILY, 100),
};

function positiveInt(raw: string | undefined, fallback: number): number {
  const parsed = Number(raw);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

type Counts = { day: string; global: number; byIp: Map<string, number> };

const holder = globalThis as unknown as { __intakeCounts?: Counts };

function today(): string {
  // Korea has no daylight saving, so a fixed offset is enough.
  return new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
}

function counts(): Counts {
  const day = today();
  if (!holder.__intakeCounts || holder.__intakeCounts.day !== day) holder.__intakeCounts = { day, global: 0, byIp: new Map() };
  return holder.__intakeCounts;
}

export type CapResult = { ok: true; ipLeft: number; globalLeft: number } | { ok: false; which: "ip" | "global" };

/** Check and count in one synchronous step, so concurrent requests cannot pass the same slot. */
export function takeSlot(ip: string): CapResult {
  const c = counts();
  if (c.global >= CAPS.globalDaily) return { ok: false, which: "global" };
  const used = c.byIp.get(ip) ?? 0;
  if (used >= CAPS.perIpDaily) return { ok: false, which: "ip" };
  c.global += 1;
  c.byIp.set(ip, used + 1);
  return { ok: true, ipLeft: CAPS.perIpDaily - used - 1, globalLeft: CAPS.globalDaily - c.global };
}
