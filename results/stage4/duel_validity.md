# A3 duel validity: the duel with no outside truth

Inside a real sample of 200: 5 fold cross validation stratified by cell, calibrated panel E4 against age and sex logistic R1, out of fold log loss. Keep only if the interval of the mean fold improvement lies wholly above zero. Stored answers only. Plan: config/prereg_stage4.json.

## Acceptance stated in advance: PASSED

Positive control control_s1.0 keep rate 1.0. Surrogate keep rates {'surrogate_terra_slot': 0.115, 'surrogate_luna_slot': 0.0}. Margin over the higher surrogate 0.885 [0.84, 0.93]. Surrogate bar met: True. Positive bar met: True.

The acceptance passed. The duel may be called a decision rule for the anchor items under row draws from this pool. No concept question has met a real survey.

## row draws, pooled decision, panel excluded truth

| panel | keep rate | interval | beats R1 on truth | kept and beats | kept, not beats | dropped and beats | dropped, not beats | false keep rate | false keep over not beating | missed keep rate | mean improvement |
|---|---|---|---|---|---|---|---|---|---|---|---|
| terra_C2 | 0.31 | [0.25, 0.37] | 0.52 | 35 | 27 | 69 | 69 | 0.4355 | 0.2812 | 0.6635 | 0.02088 |
| luna_C1 | 0.015 | [0.0, 0.035] | 0.425 | 2 | 1 | 83 | 114 | 0.3333 | 0.0087 | 0.9765 | 0.00837 |
| control_s0.25 | 0.955 | [0.925, 0.98] | 0.865 | 166 | 25 | 7 | 2 | 0.1309 | 0.9259 | 0.0405 | 0.07315 |
| control_s0.5 | 0.99 | [0.975, 1.0] | 0.945 | 188 | 10 | 1 | 1 | 0.0505 | 0.9091 | 0.0053 | 0.12321 |
| control_s1.0 | 1.0 | [1.0, 1.0] | 0.965 | 193 | 7 | 0 | 0 | 0.035 | 1.0 | 0.0 | 0.21118 |
| control_s2.0 | 1.0 | [1.0, 1.0] | 0.995 | 199 | 1 | 0 | 0 | 0.005 | 1.0 | 0.0 | 0.32148 |
| surrogate_terra_slot | 0.115 | [0.07, 0.16] | 0.665 | 13 | 10 | 120 | 57 | 0.4348 | 0.1493 | 0.9023 | 0.01262 |
| surrogate_luna_slot | 0.0 | [0.0, 0.0] | 0.305 | 0 | 0 | 61 | 139 | None | 0.0 | 1.0 | -0.0168 |

### row draws, per item keep rate on the same rule

| panel | ever | weekly | carb |
|---|---|---|---|
| terra_C2 | 0.065 | 0.515 | 0.045 |
| luna_C1 | 0.0 | 0.125 | 0.045 |
| control_s0.25 | 0.99 | 0.95 | 0.38 |
| control_s0.5 | 1.0 | 0.99 | 0.575 |
| control_s1.0 | 1.0 | 1.0 | 0.765 |
| control_s2.0 | 1.0 | 1.0 | 0.785 |
| surrogate_terra_slot | 0.025 | 0.09 | 0.045 |
| surrogate_luna_slot | 0.0 | 0.0 | 0.0 |

### row draws, whole test truth sensitivity, pooled

| panel | beats R1 | false keep rate | missed keep rate |
|---|---|---|---|
| terra_C2 | 0.59 | 0.4032 | 0.6864 |
| luna_C1 | 0.29 | 0.3333 | 0.9655 |
| control_s0.25 | 0.955 | 0.0471 | 0.0471 |
| control_s0.5 | 0.99 | 0.0101 | 0.0101 |
| control_s1.0 | 1.0 | 0.0 | 0.0 |
| control_s2.0 | 1.0 | 0.0 | 0.0 |
| surrogate_terra_slot | 0.665 | 0.3043 | 0.8797 |
| surrogate_luna_slot | 0.28 | None | 1.0 |

## cluster draws, pooled decision, panel excluded truth (sensitivity, not read by the acceptance)

| panel | keep rate | interval | beats R1 on truth | kept and beats | kept, not beats | dropped and beats | dropped, not beats | false keep rate | false keep over not beating | missed keep rate | mean improvement |
|---|---|---|---|---|---|---|---|---|---|---|---|
| terra_C2 | 0.32 | [0.255, 0.39] | 0.57 | 34 | 30 | 80 | 56 | 0.4688 | 0.3488 | 0.7018 | 0.02423 |
| luna_C1 | 0.025 | [0.005, 0.05] | 0.415 | 1 | 4 | 82 | 113 | 0.8 | 0.0342 | 0.988 | 0.01149 |
| control_s0.25 | 0.935 | [0.9, 0.97] | 0.83 | 155 | 32 | 11 | 2 | 0.1711 | 0.9412 | 0.0663 | 0.07664 |
| control_s0.5 | 0.98 | [0.96, 0.995] | 0.98 | 192 | 4 | 4 | 0 | 0.0204 | 1.0 | 0.0204 | 0.12544 |
| control_s1.0 | 0.995 | [0.985, 1.0] | 0.995 | 198 | 1 | 1 | 0 | 0.005 | 1.0 | 0.005 | 0.21321 |
| control_s2.0 | 1.0 | [1.0, 1.0] | 1.0 | 200 | 0 | 0 | 0 | 0.0 | None | 0.0 | 0.32236 |
| surrogate_terra_slot | 0.1 | [0.06, 0.1401] | 0.56 | 8 | 12 | 104 | 76 | 0.6 | 0.1364 | 0.9286 | 0.01646 |
| surrogate_luna_slot | 0.0 | [0.0, 0.0] | 0.34 | 0 | 0 | 68 | 132 | None | 0.0 | 1.0 | -0.01329 |

### cluster draws, per item keep rate on the same rule

| panel | ever | weekly | carb |
|---|---|---|---|
| terra_C2 | 0.085 | 0.445 | 0.04 |
| luna_C1 | 0.01 | 0.115 | 0.04 |
| control_s0.25 | 0.96 | 0.82 | 0.3 |
| control_s0.5 | 1.0 | 0.935 | 0.475 |
| control_s1.0 | 1.0 | 0.935 | 0.67 |
| control_s2.0 | 1.0 | 0.955 | 0.71 |
| surrogate_terra_slot | 0.0 | 0.135 | 0.045 |
| surrogate_luna_slot | 0.0 | 0.005 | 0.0 |

### cluster draws, whole test truth sensitivity, pooled

| panel | beats R1 | false keep rate | missed keep rate |
|---|---|---|---|
| terra_C2 | 0.605 | 0.4375 | 0.7025 |
| luna_C1 | 0.325 | 0.8 | 0.9846 |
| control_s0.25 | 0.89 | 0.107 | 0.0618 |
| control_s0.5 | 0.99 | 0.0102 | 0.0202 |
| control_s1.0 | 1.0 | 0.0 | 0.005 |
| control_s2.0 | 1.0 | 0.0 | 0.0 |
| surrogate_terra_slot | 0.54 | 0.55 | 0.9167 |
| surrogate_luna_slot | 0.335 | None | 1.0 |

## Limits

- Anchor items with KREI answers. No concept question has met a real survey.
- 5 fold intervals share training rows, so their nominal coverage is not exact. The keep rates above are the measured behaviour.
- The surrogate's age and sex model was fit on the train split, far more rows than 200, so it can beat R1 on truth without any LLM.
- Folds do not keep survey units whole, as the plan asked.
