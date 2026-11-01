# Trust map v1, v2, v3 side by side

**v3 was written after the answers were seen. It is not pre-registered.** v1 and v2 are unchanged. A raw panel number is never a market number under any label.

## Acceptance: PASSED

Bar: the real answer control must obtain 보정 후 참고 on at least 2 of 3 items in each of the 4 slots, and the non-LLM stand-in panel on at most 1 of 12.

Real answer control per slot: {"gpt-6.1-terra|C2": {"items": 3, "calibrated": ["weekly", "carb"]}, "gpt-6.1-terra|C1": {"items": 3, "calibrated": ["weekly", "carb"]}, "gpt-6-luna|C2": {"items": 3, "calibrated": ["weekly", "carb"]}, "gpt-6-luna|C1": {"items": 3, "calibrated": ["weekly", "carb"]}}. The 4 slots hold the same answers, so this is one result shown 4 times.
Stand-in panel rows with 보정 후 참고: none.

The bar was met. This shows the first branch can fire for a panel holding the real answers and not for a stand-in panel on age and sex at these seeds. The rule was still written after the answers, so a label here is a reading of data already seen.

## LLM answers, stage 2

Counts: v1 {'보정 후 참고': 12}, v2 {'방향만': 8, '실측 전용': 4}, v3 {'방향만': 8, '판정 불가': 4}. 성별 차이 사용 금지: 6 of 12 at the stage 2 seed, {'stage2_seed': 6, 'alt_seed_99': 6, 'alt_seed_20261102': 5} across seeds.

| item | model | cond | v1 | v2 | v3 | v3 estimators | 성별 차이 사용 금지 | E4-R1 row | E4-R1 cluster mean |
|---|---|---|---|---|---|---|---|---|---|
| ever | gpt-6.1-terra | C2 | 보정 후 참고 | 방향만 | 방향만 | - | True | +1.25 [-0.69,+2.87] | +0.80 |
| weekly | gpt-6.1-terra | C2 | 보정 후 참고 | 방향만 | 방향만 | - | False | -0.55 [-1.70,+0.32] | -0.77 |
| carb | gpt-6.1-terra | C2 | 보정 후 참고 | 실측 전용 | 판정 불가 | - | False | -0.86 [-2.40,+0.08] | -0.63 |
| ever | gpt-6.1-terra | C1 | 보정 후 참고 | 방향만 | 방향만 | - | True | +1.46 [-0.44,+3.06] | +1.05 |
| weekly | gpt-6.1-terra | C1 | 보정 후 참고 | 방향만 | 방향만 | - | True | -0.20 [-1.32,+0.56] | -0.47 |
| carb | gpt-6.1-terra | C1 | 보정 후 참고 | 실측 전용 | 판정 불가 | - | False | -0.82 [-2.38,+0.11] | -0.58 |
| ever | gpt-6-luna | C2 | 보정 후 참고 | 방향만 | 방향만 | - | True | +1.98 [-0.10,+3.70] | +1.71 |
| weekly | gpt-6-luna | C2 | 보정 후 참고 | 방향만 | 방향만 | - | True | -0.20 [-1.31,+0.75] | -0.48 |
| carb | gpt-6-luna | C2 | 보정 후 참고 | 실측 전용 | 판정 불가 | - | False | -0.94 [-2.71,+0.12] | -0.71 |
| ever | gpt-6-luna | C1 | 보정 후 참고 | 방향만 | 방향만 | - | True | +1.19 [-0.85,+2.96] | +1.00 |
| weekly | gpt-6-luna | C1 | 보정 후 참고 | 방향만 | 방향만 | - | False | -0.10 [-1.15,+0.76] | -0.38 |
| carb | gpt-6-luna | C1 | 보정 후 참고 | 실측 전용 | 판정 불가 | - | False | -0.87 [-2.63,+0.18] | -0.64 |

## Real answer control

Each respondent's real answer stands in as the panel's answer in every slot. The 4 slots are identical by construction, so they are one result shown 4 times. Not a claim about any LLM.

Counts: v1 {'보정 후 참고': 12}, v2 {'방향만': 8, '실측 전용': 4}, v3 {'방향만': 4, '보정 후 참고': 8}.

| item | model | cond | v1 | v2 | v3 | v3 estimators | 성별 차이 사용 금지 | E4-R1 row | E4-R1 cluster mean |
|---|---|---|---|---|---|---|---|---|---|
| ever | gpt-6.1-terra | C2 | 보정 후 참고 | 방향만 | 방향만 | - | False | -1.98 [-4.69,+0.35] | -3.13 |
| weekly | gpt-6.1-terra | C2 | 보정 후 참고 | 방향만 | 보정 후 참고 | E4,E5,E6 | False | -2.55 [-4.88,-0.18] | -3.65 |
| carb | gpt-6.1-terra | C2 | 보정 후 참고 | 실측 전용 | 보정 후 참고 | E4,E5,E6 | False | -1.53 [-3.21,-0.22] | -1.84 |

## Non-LLM stand-in panel

Train split age and sex logistic plus a shift and noise, rng seed 1. It holds no LLM answer and no information beyond age and sex.

Counts: v1 {'보정 후 참고': 11, '방향만': 1}, v2 {'방향만': 4, '실측 전용': 8}, v3 {'방향만': 4, '실측 전용': 4, '판정 불가': 4}.

| item | model | cond | v1 | v2 | v3 | v3 estimators | 성별 차이 사용 금지 | E4-R1 row | E4-R1 cluster mean |
|---|---|---|---|---|---|---|---|---|---|
| ever | gpt-6.1-terra | C2 | 보정 후 참고 | 방향만 | 방향만 | - | False | -0.30 [-2.47,+1.41] | -0.14 |
| weekly | gpt-6.1-terra | C2 | 보정 후 참고 | 실측 전용 | 실측 전용 | - | True | +0.43 [-1.15,+1.39] | +0.16 |
| carb | gpt-6.1-terra | C2 | 보정 후 참고 | 실측 전용 | 판정 불가 | - | False | -0.69 [-2.06,+0.44] | -0.59 |
| ever | gpt-6.1-terra | C1 | 보정 후 참고 | 방향만 | 방향만 | - | False | +0.05 [-1.95,+1.69] | +0.08 |
| weekly | gpt-6.1-terra | C1 | 보정 후 참고 | 실측 전용 | 실측 전용 | - | False | +0.58 [-0.94,+1.63] | +0.35 |
| carb | gpt-6.1-terra | C1 | 보정 후 참고 | 실측 전용 | 판정 불가 | - | False | -0.59 [-1.94,+0.53] | -0.48 |
| ever | gpt-6-luna | C2 | 보정 후 참고 | 방향만 | 방향만 | - | False | +0.19 [-1.78,+1.78] | +0.29 |
| weekly | gpt-6-luna | C2 | 보정 후 참고 | 실측 전용 | 실측 전용 | - | False | +0.82 [-0.93,+1.89] | +0.52 |
| carb | gpt-6-luna | C2 | 보정 후 참고 | 실측 전용 | 판정 불가 | - | False | -0.50 [-1.95,+0.59] | -0.41 |
| ever | gpt-6-luna | C1 | 보정 후 참고 | 방향만 | 방향만 | - | False | +0.47 [-1.75,+2.82] | +0.65 |
| weekly | gpt-6-luna | C1 | 방향만 | 실측 전용 | 실측 전용 | - | False | +0.81 [-1.04,+2.06] | +0.47 |
| carb | gpt-6-luna | C1 | 보정 후 참고 | 실측 전용 | 판정 불가 | - | False | -0.64 [-2.06,+0.39] | -0.52 |

## Stand-in panels told part of each real answer, relabelled from stored inputs

| strength | item | AUC | v2 | v3 |
|---|---|---|---|---|
| control_s0.25 | ever | 0.8542 | 방향만 | 방향만 |
| control_s0.25 | weekly | 0.8357 | 실측 전용 | 실측 전용 |
| control_s0.25 | carb | 0.7989 | 실측 전용 | 판정 불가 |
| control_s0.5 | ever | 0.9174 | 방향만 | 방향만 |
| control_s0.5 | weekly | 0.9199 | 실측 전용 | 실측 전용 |
| control_s0.5 | carb | 0.9157 | 실측 전용 | 판정 불가 |
| control_s1.0 | ever | 0.9863 | 방향만 | 방향만 |
| control_s1.0 | weekly | 0.9713 | 실측 전용 | 실측 전용 |
| control_s1.0 | carb | 0.9896 | 실측 전용 | 판정 불가 |
| control_s2.0 | ever | 1.0 | 방향만 | 방향만 |
| control_s2.0 | weekly | 0.9946 | 방향만 | 보정 후 참고 |
| control_s2.0 | carb | 1.0 | 실측 전용 | 보정 후 참고 |

## Seed sensitivity

```
{
 "alt_seed_99": {
  "real_answers_calibrated": [
   "weekly",
   "carb"
  ],
  "surrogate_rows_calibrated": [],
  "passed": true
 },
 "alt_seed_20261102": {
  "real_answers_calibrated": [
   "weekly",
   "carb"
  ],
  "surrogate_rows_calibrated": [],
  "passed": true
 }
}
```

LLM labels across seeds:

```
{
 "stage2_seed": {
  "gpt-6.1-terra|C2|ever": "방향만",
  "gpt-6.1-terra|C2|weekly": "방향만",
  "gpt-6.1-terra|C2|carb": "판정 불가",
  "gpt-6.1-terra|C1|ever": "방향만",
  "gpt-6.1-terra|C1|weekly": "방향만",
  "gpt-6.1-terra|C1|carb": "판정 불가",
  "gpt-6-luna|C2|ever": "방향만",
  "gpt-6-luna|C2|weekly": "방향만",
  "gpt-6-luna|C2|carb": "판정 불가",
  "gpt-6-luna|C1|ever": "방향만",
  "gpt-6-luna|C1|weekly": "방향만",
  "gpt-6-luna|C1|carb": "판정 불가"
 },
 "alt_seed_99": {
  "gpt-6.1-terra|C2|ever": "방향만",
  "gpt-6.1-terra|C2|weekly": "방향만",
  "gpt-6.1-terra|C2|carb": "판정 불가",
  "gpt-6.1-terra|C1|ever": "방향만",
  "gpt-6.1-terra|C1|weekly": "방향만",
  "gpt-6.1-terra|C1|carb": "판정 불가",
  "gpt-6-luna|C2|ever": "방향만",
  "gpt-6-luna|C2|weekly": "방향만",
  "gpt-6-luna|C2|carb": "판정 불가",
  "gpt-6-luna|C1|ever": "방향만",
  "gpt-6-luna|C1|weekly": "방향만",
  "gpt-6-luna|C1|carb": "판정 불가"
 },
 "alt_seed_20261102": {
  "gpt-6.1-terra|C2|ever": "방향만",
  "gpt-6.1-terra|C2|weekly": "방향만",
  "gpt-6.1-terra|C2|carb": "판정 불가",
  "gpt-6.1-terra|C1|ever": "방향만",
  "gpt-6.1-terra|C1|weekly": "방향만",
  "gpt-6.1-terra|C1|carb": "판정 불가",
  "gpt-6-luna|C2|ever": "방향만",
  "gpt-6-luna|C2|weekly": "방향만",
  "gpt-6-luna|C2|carb": "판정 불가",
  "gpt-6-luna|C1|ever": "방향만",
  "gpt-6-luna|C1|weekly": "방향만",
  "gpt-6-luna|C1|carb": "판정 불가"
 }
}
```

Gender flag rows that change with the seed: ['gpt-6.1-terra|C1|weekly'].

## Limits

- Intervals are across 200 draws with the pool and the test panel held fixed. No correction across 12 combinations and 3 estimators.
- The panel holds 0.5856 of the test split's psfwt. All R1 comparisons here use the truth from the other 1321 test rows only.
- The first branch now takes a row interval and a cluster mean. The cluster interval still includes zero for the real answer control, so the branch is weaker than v2's on purpose.
- The branch still needs close to the real answers. In the relabelled controls above it fires only at the strongest strength. A missing first label on an LLM answer is therefore no evidence of an LLM failure, and passing the bar is no evidence that a label separates good panels from weak ones at ordinary signal.
- The other branches do not separate panels either. carb is undecidable for every panel that misses the first branch, because the real slope interval includes zero. The weekly difference between the LLM answers and the stand-in panel comes from the underdispersion check and the stand-in's shift.
