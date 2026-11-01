# Trust map v1 and v2 side by side

v1 is src/lotte_audit/verdict.py, unchanged. Its level_trusted field is shown as beats_e2: it only ever meant the estimator beat the shrunk cell mean E2.

**v2 is not pre-registered with respect to the stage 2 answers.** It was written after they were seen, because v1 gave all 12 combinations one label and a non-LLM stand-in panel took 11 of 12. No correction across the 12 combinations and 3 estimators. Intervals are across 200 draws with the pool and the test panel held fixed; they do not carry the sampling uncertainty of those.

v2 reads R1 and all real-side quantities on the truth from test respondents outside the 1000 panel, which is smaller and noisier than the whole test truth. A raw panel number is never a market number under any label.

## Stage 2 answers

v1 counts: {'보정 후 참고': 12}. v2 counts: {'방향만': 8, '실측 전용': 4}. 성별 차이 사용 금지: 6 of 12. Stored stage 2 v1 labels reproduced: True.

| item | model | cond | v1 label | v1 beats_e2 | v2 label | v2 estimators beating R1 | 성별 차이 사용 금지 | slope ok | cell r ok | underdisp ok |
|---|---|---|---|---|---|---|---|---|---|---|
| ever | gpt-6.1-terra | C2 | 보정 후 참고 | True | 방향만 | - | True | True | True | True |
| weekly | gpt-6.1-terra | C2 | 보정 후 참고 | True | 방향만 | - | False | True | True | True |
| carb | gpt-6.1-terra | C2 | 보정 후 참고 | True | 실측 전용 | - | False | False | False | True |
| ever | gpt-6.1-terra | C1 | 보정 후 참고 | True | 방향만 | - | True | True | True | True |
| weekly | gpt-6.1-terra | C1 | 보정 후 참고 | True | 방향만 | - | True | True | True | True |
| carb | gpt-6.1-terra | C1 | 보정 후 참고 | True | 실측 전용 | - | False | False | False | True |
| ever | gpt-6-luna | C2 | 보정 후 참고 | True | 방향만 | - | True | True | True | True |
| weekly | gpt-6-luna | C2 | 보정 후 참고 | True | 방향만 | - | True | True | True | True |
| carb | gpt-6-luna | C2 | 보정 후 참고 | True | 실측 전용 | - | False | False | False | True |
| ever | gpt-6-luna | C1 | 보정 후 참고 | True | 방향만 | - | True | True | True | True |
| weekly | gpt-6-luna | C1 | 보정 후 참고 | True | 방향만 | - | False | True | True | True |
| carb | gpt-6-luna | C1 | 보정 후 참고 | True | 실측 전용 | - | False | False | False | True |

### v2 inputs, truth outside the panel. Negative E-R1 means the estimator is better than R1

| item | model | cond | E4-R1 row | E5-R1 row | E6-R1 row | E4-R1 cluster | E5-R1 cluster | E6-R1 cluster | panel slope | real slope CI | cell r | underdisp | gender gap panel | gender gap real | panel minus real |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ever | gpt-6.1-terra | C2 | +1.25 [-0.69,+2.87] | +1.23 [-0.45,+2.69] | +2.12 [-0.25,+4.01] | +0.80 [-2.57,+2.77] | +0.87 [-1.26,+2.79] | +2.00 [-1.59,+4.46] | -9.35 | [-15.40,-10.43] | 0.938 | 0.721 | -4.61 | +3.31 | [-14.34,-1.23] |
| weekly | gpt-6.1-terra | C2 | -0.55 [-1.70,+0.32] | -0.38 [-1.59,+0.48] | +0.56 [-0.62,+1.65] | -0.77 [-2.59,+0.10] | -0.44 [-2.04,+1.16] | +0.25 [-1.94,+1.74] | -7.20 | [-5.30,-1.40] | 0.802 | 1.73 | -4.10 | -0.34 | [-8.35,+0.72] |
| carb | gpt-6.1-terra | C2 | -0.86 [-2.40,+0.08] | -0.23 [-1.39,+0.55] | +0.38 [-0.62,+1.27] | -0.63 [-2.60,+0.16] | -0.12 [-1.32,+0.90] | +0.17 [-1.34,+1.29] | -3.50 | [-2.60,+0.51] | 0.596 | 1.504 | -5.94 | -5.63 | [-4.48,+3.93] |
| ever | gpt-6.1-terra | C1 | +1.46 [-0.44,+3.06] | +1.46 [-0.27,+2.81] | +2.44 [-0.03,+4.41] | +1.05 [-2.19,+2.87] | +1.09 [-0.83,+2.69] | +2.27 [-1.40,+4.92] | -9.44 | [-15.40,-10.43] | 0.925 | 0.74 | -4.99 | +3.31 | [-14.49,-1.78] |
| weekly | gpt-6.1-terra | C1 | -0.20 [-1.32,+0.56] | -0.14 [-1.14,+0.64] | +1.01 [-0.20,+2.03] | -0.47 [-2.28,+0.30] | -0.25 [-1.22,+0.69] | +0.66 [-1.87,+2.12] | -7.35 | [-5.30,-1.40] | 0.778 | 1.774 | -4.91 | -0.34 | [-9.05,-0.14] |
| carb | gpt-6.1-terra | C1 | -0.82 [-2.38,+0.11] | -0.17 [-1.31,+0.68] | +0.42 [-0.56,+1.30] | -0.58 [-2.53,+0.23] | -0.07 [-1.20,+1.09] | +0.24 [-1.35,+1.41] | -3.46 | [-2.60,+0.51] | 0.569 | 1.463 | -5.52 | -5.63 | [-4.08,+4.33] |
| ever | gpt-6-luna | C2 | +1.98 [-0.10,+3.70] | +1.65 [-0.94,+4.00] | +2.83 [+0.39,+4.95] | +1.71 [-1.83,+3.85] | +1.75 [-2.55,+5.30] | +2.77 [-1.33,+5.50] | -8.12 | [-15.40,-10.43] | 0.907 | 0.65 | -4.62 | +3.31 | [-14.12,-1.37] |
| weekly | gpt-6-luna | C2 | -0.20 [-1.31,+0.75] | -0.05 [-1.14,+0.81] | +0.55 [-0.51,+1.48] | -0.48 [-2.34,+0.42] | -0.28 [-1.73,+1.04] | +0.23 [-1.83,+1.56] | -6.17 | [-5.30,-1.40] | 0.733 | 1.508 | -5.16 | -0.34 | [-9.46,-0.37] |
| carb | gpt-6-luna | C2 | -0.94 [-2.71,+0.12] | -0.73 [-2.30,+0.21] | -0.31 [-1.40,+0.62] | -0.71 [-2.96,+0.23] | -0.47 [-2.48,+0.48] | -0.42 [-1.86,+0.55] | -2.06 | [-2.60,+0.51] | 0.665 | 0.944 | -4.82 | -5.63 | [-3.35,+5.05] |
| ever | gpt-6-luna | C1 | +1.19 [-0.85,+2.96] | +0.62 [-1.40,+2.78] | +2.51 [-0.11,+4.73] | +1.00 [-2.48,+2.81] | +0.72 [-2.73,+2.91] | +2.46 [-1.60,+4.79] | -9.36 | [-15.40,-10.43] | 0.908 | 0.755 | -5.01 | +3.31 | [-14.74,-1.59] |
| weekly | gpt-6-luna | C1 | -0.10 [-1.15,+0.76] | -0.05 [-1.02,+0.83] | +0.77 [-0.26,+1.70] | -0.38 [-2.40,+0.52] | -0.19 [-1.48,+1.07] | +0.36 [-1.90,+1.74] | -6.35 | [-5.30,-1.40] | 0.747 | 1.551 | -4.63 | -0.34 | [-8.84,+0.30] |
| carb | gpt-6-luna | C1 | -0.87 [-2.63,+0.18] | -0.34 [-1.78,+0.64] | -0.26 [-1.32,+0.62] | -0.64 [-2.89,+0.30] | -0.23 [-1.73,+0.65] | -0.34 [-1.85,+0.67] | -1.98 | [-2.60,+0.51] | 0.646 | 0.914 | -4.84 | -5.63 | [-3.35,+5.10] |

Sensitivity: labels that would differ if v2 read the whole test truth instead: 4.

## Non-LLM stand-in panel, the stage 2 test

Train split age and sex logistic plus a shift and noise, rng seed 1. It holds no LLM answer and no information beyond age and sex.

v1 counts: {'보정 후 참고': 11, '방향만': 1}. v2 counts: {'방향만': 4, '실측 전용': 8}. Stage 2 recorded 11 of 12 and 1 of 12 under v1.

| item | model | cond | v1 label | v1 beats_e2 | v2 label | v2 estimators beating R1 | 성별 차이 사용 금지 | slope ok | cell r ok | underdisp ok |
|---|---|---|---|---|---|---|---|---|---|---|
| ever | gpt-6.1-terra | C2 | 보정 후 참고 | True | 방향만 | - | False | True | True | True |
| weekly | gpt-6.1-terra | C2 | 보정 후 참고 | True | 실측 전용 | - | True | True | True | False |
| carb | gpt-6.1-terra | C2 | 보정 후 참고 | True | 실측 전용 | - | False | False | False | False |
| ever | gpt-6.1-terra | C1 | 보정 후 참고 | True | 방향만 | - | False | True | True | True |
| weekly | gpt-6.1-terra | C1 | 보정 후 참고 | True | 실측 전용 | - | False | True | True | False |
| carb | gpt-6.1-terra | C1 | 보정 후 참고 | True | 실측 전용 | - | False | False | False | False |
| ever | gpt-6-luna | C2 | 보정 후 참고 | True | 방향만 | - | False | True | True | True |
| weekly | gpt-6-luna | C2 | 보정 후 참고 | True | 실측 전용 | - | False | True | True | False |
| carb | gpt-6-luna | C2 | 보정 후 참고 | True | 실측 전용 | - | False | False | False | False |
| ever | gpt-6-luna | C1 | 보정 후 참고 | True | 방향만 | - | False | True | True | True |
| weekly | gpt-6-luna | C1 | 방향만 | False | 실측 전용 | - | False | True | True | False |
| carb | gpt-6-luna | C1 | 보정 후 참고 | True | 실측 전용 | - | False | False | False | False |

## Positive control: stand-in panels told part of each real answer

Shows whether the first branch of v2 can fire at all. Not a claim about any LLM. AUC is on the 1000 test panel; Terra C2 for comparison is in results/main/main_score.md.

| strength | item | AUC | v1 label | v2 label | v2 estimators beating R1 | E4-R1 row | E4-R1 cluster |
|---|---|---|---|---|---|---|---|
| control_s0.25 | ever | 0.8542 | 보정 후 참고 | 방향만 | - | -0.62 [-2.76,+1.12] | -0.86 [-4.29,+1.00] |
| control_s0.25 | weekly | 0.8357 | 보정 후 참고 | 실측 전용 | - | +0.22 [-1.21,+1.14] | -0.17 [-2.32,+1.30] |
| control_s0.25 | carb | 0.7989 | 보정 후 참고 | 실측 전용 | - | -0.87 [-2.24,+0.20] | -0.73 [-2.53,+0.23] |
| control_s0.5 | ever | 0.9174 | 보정 후 참고 | 방향만 | - | -1.08 [-3.14,+0.60] | -1.47 [-4.36,+0.64] |
| control_s0.5 | weekly | 0.9199 | 보정 후 참고 | 실측 전용 | - | +0.03 [-1.33,+0.96] | -0.48 [-2.45,+0.77] |
| control_s0.5 | carb | 0.9157 | 보정 후 참고 | 실측 전용 | - | -0.80 [-2.12,+0.34] | -0.75 [-2.38,+0.44] |
| control_s1.0 | ever | 0.9863 | 보정 후 참고 | 방향만 | - | -1.70 [-3.70,+0.18] | -2.37 [-5.65,+0.05] |
| control_s1.0 | weekly | 0.9713 | 보정 후 참고 | 실측 전용 | - | +0.05 [-1.11,+1.13] | -0.79 [-2.95,+0.76] |
| control_s1.0 | carb | 0.9896 | 보정 후 참고 | 실측 전용 | - | -0.79 [-2.09,+0.38] | -0.85 [-2.52,+0.49] |
| control_s2.0 | ever | 1.0 | 보정 후 참고 | 방향만 | - | -2.15 [-5.05,+0.26] | -3.23 [-8.82,+0.15] |
| control_s2.0 | weekly | 0.9946 | 보정 후 참고 | 방향만 | - | -0.89 [-2.61,+0.68] | -2.01 [-5.72,+0.54] |
| control_s2.0 | carb | 1.0 | 보정 후 참고 | 실측 전용 | - | -1.03 [-2.50,+0.26] | -1.24 [-2.95,+0.63] |
