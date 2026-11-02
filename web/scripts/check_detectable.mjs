// The slider's arithmetic against the stored file. Run with:
//   node --experimental-strip-types web/scripts/check_detectable.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import assert from "node:assert/strict";
import { neededPerCard, smallestGap } from "../lib/detectable.ts";

const here = dirname(fileURLToPath(import.meta.url));
const site = JSON.parse(readFileSync(join(here, "..", "data", "stage4.json"), "utf8")).detectable;
const stored = JSON.parse(readFileSync(join(here, "..", "..", "results", "stage4", "detectable.json"), "utf8"));
assert.deepEqual(site, stored);

assert.equal(smallestGap(stored.n_arm, stored), stored.between_mde_pp);
assert.equal(stored.n_total, stored.n_arm * 2);
for (const row of stored.needed) {
  assert.equal(neededPerCard(row.gap_pp, stored), row.between_per_arm);
  assert.equal(row.between_total, row.between_per_arm * 2);
  assert.equal(smallestGap(row.between_per_arm, stored), row.gap_pp);
}
console.log("detectable ok", smallestGap(100, stored), smallestGap(393, stored), smallestGap(1570, stored));
