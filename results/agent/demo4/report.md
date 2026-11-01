manifest sha256: 4b21fe64410fbfc560486250e33e41b24d782b79295b3a254ed46b996ef5ccdb

# 시연 전용, 정답 없음. 모든 카드는 가상이며 A_brand는 브랜드 효과 측정용 문구로 실제 제품이나 계획이 아닙니다.

구매 의향 값은 패널 내부 값입니다. 시장 수치나 판매 전망이 아니며, 그렇게 쓰지 않습니다.

## 검증하지 못한 것

- 측정한 것은 기존 음료 행동의 재현입니다. 새 콘셉트 반응의 정확도는 재지 않았습니다.
- 이 시연에는 정답이 없습니다. 아래 진단은 실행 안의 잡음을 재는 것이며, 어느 안이 실제로 낫다는 증거가 아닙니다.
- 기반 판정의 규칙 v2는 2단계 답을 본 뒤에 썼으므로 그 답에 대해 사전 등록이 아닙니다.
- 바꿔 쓴 카드는 후보 A 하나뿐이라, 이 잡음이 다른 후보에도 같다고 가정합니다.
- 칠성 내부 자료는 쓰지 않았습니다. 전단 필터 효용은 첫 시범의 되살림 검증으로 재야 합니다.

## 빠진 요청 항목

빠진 요청 항목 없음.

## verdict

판정은 코드가 내고, 임계값은 답을 보기 전에 고정했습니다.

- terra에서 브랜드 표시 효과는 바꿔 쓴 차이를 넘지 않았습니다.
- terra에서 후보 A와 B의 차이는 같은 안을 바꿔 쓴 차이를 넘습니다. 이 칸의 사용 범위는 판정표를 따릅니다.
- terra에서 후보 A와 C의 차이는 같은 안을 바꿔 쓴 차이를 넘습니다. 이 칸의 사용 범위는 판정표를 따릅니다.
- terra에서 후보 B와 C의 차이는 같은 안을 바꿔 쓴 차이를 넘습니다. 이 칸의 사용 범위는 판정표를 따릅니다.
- 후보 A는 terra all에서 실측 전용입니다.
- 후보 B는 terra all에서 실측 전용입니다.
- 후보 C는 terra all에서 방향만입니다.
- luna에서 브랜드 표시 효과가 바꿔 쓴 차이보다 커서 절대값을 숨깁니다.
- luna에서 후보 A와 B의 차이는 같은 안을 바꿔 쓴 차이 안에 있어 구분 불가입니다.
- luna에서 후보 A와 C의 차이는 같은 안을 바꿔 쓴 차이를 넘습니다. 이 칸의 사용 범위는 판정표를 따릅니다.
- luna에서 후보 B와 C의 차이는 같은 안을 바꿔 쓴 차이를 넘습니다. 이 칸의 사용 범위는 판정표를 따릅니다.
- 후보 A는 luna all에서 실측 전용입니다.
- 후보 B는 luna all에서 실측 전용입니다.
- 후보 C는 luna all에서 방향만입니다.
- 페르소나 없는 조건과 순위나 간격이 달랐습니다. 이 차이가 실제 응답에 더 가깝다는 뜻은 아닙니다.

| card | model | segment | n | v2 base | run status | label | absolute shown | order allowed | flags |
|---|---|---|---|---|---|---|---|---|---|
| A | terra | all | 150 | 실측 전용 | 유효 | 실측 전용 | False | False | 성별 차이 사용 금지 |
| B | terra | all | 150 | 실측 전용 | 유효 | 실측 전용 | False | False | 성별 차이 사용 금지 |
| C | terra | all | 150 | 방향만 | 유효 | 방향만 | True | False | 성별 차이 사용 금지 |
| A | luna | all | 150 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 절대값 숨김, 성별 차이 사용 금지 |
| B | luna | all | 150 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 절대값 숨김, 성별 차이 사용 금지 |
| C | luna | all | 150 | 방향만 | 유효 | 방향만 | False | False | 절대값 숨김, 성별 차이 사용 금지 |

### by segment

| card | model | segment | n | v2 base | run status | label | absolute shown | order allowed | flags |
|---|---|---|---|---|---|---|---|---|---|
| A | terra | all | 150 | 실측 전용 | 유효 | 실측 전용 | False | False | 성별 차이 사용 금지 |
| A | terra | 19-39_f | 19 | 실측 전용 | 미확정 | 실측 전용 | False | False | 응답자 수 부족, 성별 차이 사용 금지 |
| A | terra | 19-39_m | 24 | 실측 전용 | 유효 | 실측 전용 | False | False | 성별 차이 사용 금지 |
| A | terra | 40-59_f | 30 | 실측 전용 | 유효 | 실측 전용 | False | False | 성별 차이 사용 금지 |
| A | terra | 40-59_m | 35 | 실측 전용 | 유효 | 실측 전용 | False | False | 성별 차이 사용 금지 |
| A | terra | 60+_f | 22 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 성별 차이 사용 금지 |
| A | terra | 60+_m | 20 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 성별 차이 사용 금지 |
| B | terra | all | 150 | 실측 전용 | 유효 | 실측 전용 | False | False | 성별 차이 사용 금지 |
| B | terra | 19-39_f | 19 | 실측 전용 | 미확정 | 실측 전용 | False | False | 응답자 수 부족, 성별 차이 사용 금지 |
| B | terra | 19-39_m | 24 | 실측 전용 | 유효 | 실측 전용 | False | False | 성별 차이 사용 금지 |
| B | terra | 40-59_f | 30 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 성별 차이 사용 금지 |
| B | terra | 40-59_m | 35 | 실측 전용 | 유효 | 실측 전용 | False | False | 성별 차이 사용 금지 |
| B | terra | 60+_f | 22 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 성별 차이 사용 금지 |
| B | terra | 60+_m | 20 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 성별 차이 사용 금지 |
| C | terra | all | 150 | 방향만 | 유효 | 방향만 | True | False | 성별 차이 사용 금지 |
| C | terra | 19-39_f | 19 | 방향만 | 미확정 | 실측 전용 | False | False | 응답자 수 부족, 성별 차이 사용 금지 |
| C | terra | 19-39_m | 24 | 방향만 | 유효 | 방향만 | True | False | 성별 차이 사용 금지 |
| C | terra | 40-59_f | 30 | 방향만 | 유효 | 방향만 | True | False | 구분 불가, 성별 차이 사용 금지 |
| C | terra | 40-59_m | 35 | 방향만 | 유효 | 방향만 | True | False | 성별 차이 사용 금지 |
| C | terra | 60+_f | 22 | 방향만 | 유효 | 방향만 | True | False | 성별 차이 사용 금지 |
| C | terra | 60+_m | 20 | 방향만 | 유효 | 방향만 | True | False | 성별 차이 사용 금지 |
| A | luna | all | 150 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 절대값 숨김, 성별 차이 사용 금지 |
| A | luna | 19-39_f | 19 | 실측 전용 | 미확정 | 실측 전용 | False | False | 응답자 수 부족, 절대값 숨김, 성별 차이 사용 금지 |
| A | luna | 19-39_m | 24 | 실측 전용 | 유효 | 실측 전용 | False | False | 절대값 숨김, 성별 차이 사용 금지 |
| A | luna | 40-59_f | 30 | 실측 전용 | 유효 | 실측 전용 | False | False | 절대값 숨김, 성별 차이 사용 금지 |
| A | luna | 40-59_m | 35 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 절대값 숨김, 성별 차이 사용 금지 |
| A | luna | 60+_f | 22 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 절대값 숨김, 성별 차이 사용 금지 |
| A | luna | 60+_m | 20 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 절대값 숨김, 성별 차이 사용 금지 |
| B | luna | all | 150 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 절대값 숨김, 성별 차이 사용 금지 |
| B | luna | 19-39_f | 19 | 실측 전용 | 미확정 | 실측 전용 | False | False | 응답자 수 부족, 절대값 숨김, 성별 차이 사용 금지 |
| B | luna | 19-39_m | 24 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 절대값 숨김, 성별 차이 사용 금지 |
| B | luna | 40-59_f | 30 | 실측 전용 | 유효 | 실측 전용 | False | False | 절대값 숨김, 성별 차이 사용 금지 |
| B | luna | 40-59_m | 35 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 절대값 숨김, 성별 차이 사용 금지 |
| B | luna | 60+_f | 22 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 절대값 숨김, 성별 차이 사용 금지 |
| B | luna | 60+_m | 20 | 실측 전용 | 유효 | 실측 전용 | False | False | 구분 불가, 절대값 숨김, 성별 차이 사용 금지 |
| C | luna | all | 150 | 방향만 | 유효 | 방향만 | False | False | 절대값 숨김, 성별 차이 사용 금지 |
| C | luna | 19-39_f | 19 | 방향만 | 미확정 | 실측 전용 | False | False | 응답자 수 부족, 절대값 숨김, 성별 차이 사용 금지 |
| C | luna | 19-39_m | 24 | 방향만 | 유효 | 방향만 | False | False | 구분 불가, 절대값 숨김, 성별 차이 사용 금지 |
| C | luna | 40-59_f | 30 | 방향만 | 유효 | 방향만 | False | False | 절대값 숨김, 성별 차이 사용 금지 |
| C | luna | 40-59_m | 35 | 방향만 | 유효 | 방향만 | False | False | 구분 불가, 절대값 숨김, 성별 차이 사용 금지 |
| C | luna | 60+_f | 22 | 방향만 | 유효 | 방향만 | False | False | 절대값 숨김, 성별 차이 사용 금지 |
| C | luna | 60+_m | 20 | 방향만 | 유효 | 방향만 | False | False | 절대값 숨김, 성별 차이 사용 금지 |

## 왜 그럴 수 있나 (가설, 근거 아님)

- 가설: A와 B의 가격 문구가 응답에서 중요한 기준으로 작용할 수 있다.
- 가설: C의 유자와 무설탕 문구는 해석하는 사람에 따라 서로 다른 기준을 떠올리게 할 수 있다.
- 가설: 모델마다 로즈메리, 복숭아, 유자의 친숙함을 다르게 반영할 수 있다.
- 가설: 브랜드 표시는 모델에 따라 가격에 대한 기대를 다르게 불러올 수 있다.
- 가설: 페르소나가 암시하는 가격 민감도가 후보별 문구의 해석에 영향을 줄 수 있다.

## 패널 이유에 자주 나온 낱말 (가설, 근거 아님)

페르소나가 쓴 이유는 응답 근거가 아닙니다. 낱말 빈도만 싣고 문장 원문은 저장소에 두지 않습니다. 빈도는 두 모델을 합친 응답 수입니다.

- A: 로즈메리 156, 매력적이지 154, 무설탕 130, 가격 129, 청귤 126, 슈거 103, 감미료 101, 있다 96
- A_para: 칼로리 213, 감미료 209, 대체 160, 가격 144, 매력적이지 143, 있습니다 82, 무설탕 73, 낯선 73
- A_brand: 가격 189, 슈거 169, 로즈메리 155, 청귤 136, 매력적이지 132, 있다 102, 조합 83, 브랜드 74
- B: 가격 243, 복숭아 182, 매력적이지 179, 탄산 161, 무설탕 158, 있다 125, 홍차 119, 망설일 91
- C: 유자 254, 가격 236, 매력적이지 144, 무설탕 117, 망설일 95, 무당 87, 있다 78, 슈거 76
- N: 가격 300, 비린 295, 배송 223, 강한 155, 음용 139, 시간 125, 비해 118, 있다 99

## diagnostics (panel internal, no truth)

이 표의 값은 규칙을 점검한 기록입니다. 실측 전용 칸의 값은 판단에 쓰지 않으며, 어느 값도 시장 수치가 아닙니다.

- terra: 후보 간 가장 큰 차이 4.1pp, 이 실행의 잡음 한계 0.882pp, 실측 200명 전체의 단일 비율 오차 ±6.9pp. 잡음을 넘는 차이도 실측에서 보일 만한 크기라는 뜻은 아닙니다.
- luna: 후보 간 가장 큰 차이 4.8pp, 이 실행의 잡음 한계 2.231pp, 실측 200명 전체의 단일 비율 오차 ±6.9pp. 잡음을 넘는 차이도 실측에서 보일 만한 크기라는 뜻은 아닙니다.

| diagnostic | terra | luna |
|---|---|---|
| paraphrase difference A minus A_para, pp | +0.24 [-0.38, +0.88] | +1.64 [+1.00, +2.23] |
| noise limit used by the rules, pp | 0.882 | 2.231 |
| candidate gap A|B, pp | -2.02 [-2.61, -1.43] distinct | -1.90 [-2.57, -1.25] indistinct |
| candidate gap A|C, pp | -4.08 [-4.66, -3.50] distinct | -4.80 [-5.50, -4.12] distinct |
| candidate gap B|C, pp | -2.06 [-2.71, -1.41] distinct | -2.90 [-3.56, -2.25] distinct |
| A minus negative control, pp | +35.85 [+34.99, +36.67] separated | +29.08 [+27.87, +30.22] separated |
| B minus negative control, pp | +37.87 [+36.86, +38.85] separated | +30.98 [+29.65, +32.22] separated |
| C minus negative control, pp | +39.93 [+39.22, +40.65] separated | +33.88 [+32.70, +34.98] separated |
| brand effect A_brand minus A, pp | -0.03 [-0.49, +0.45] within noise | +2.33 [+1.66, +3.06] exceeds noise |
| rank by panel internal value | C > B > A | C > B > A |
| missing share per card | A 0.0, A_para 0.0, A_brand 0.0, B 0.0, C 0.0, N 0.0 | A 0.0, A_para 0.0, A_brand 0.0, B 0.0, C 0.0, N 0.0 |

Model disagreement pairs: none. Ranks: {'gpt-6.1-terra': ['C', 'B', 'A'], 'gpt-6-luna': ['C', 'B', 'A']}.

No-persona comparison on terra, calls per card {'A': 10, 'A_para': 10, 'B': 10, 'C': 10, 'N': 10}. C0 rank ['C', 'B', 'A'], C1 rank ['C', 'B', 'A'], same rank True, flag no personal information False.

| pair | C1 gap | C0 gap | C1 minus C0 | within noise |
|---|---|---|---|---|
| A|B | -2.02 | -2.2 | 0.18 | True |
| A|C | -4.08 | -3.0 | -1.08 | False |
| B|C | -2.06 | -0.8 | -1.26 | False |

## real sample plan

패널은 탈락을 확정하지 못합니다. 아래는 제안이며 실측 대상은 담당자가 고릅니다.

Target segment 19-39: 140 respondents. Rest: 60.

| group | n | margin pp | arithmetic |
|---|---|---|---|
| total | 200 | 6.9 | 1.96 x sqrt(0.5 x 0.5 / 200) x 100 = 6.9pp |
| target | 140 | 8.3 | 1.96 x sqrt(0.5 x 0.5 / 140) x 100 = 8.3pp |
| rest | 60 | 12.7 | 1.96 x sqrt(0.5 x 0.5 / 60) x 100 = 12.7pp |
| 6 cells even | 33 | 17.1 | 1.96 x sqrt(0.5 x 0.5 / 33) x 100 = 17.1pp |
| 12 cells even | 16 | 24.5 | 1.96 x sqrt(0.5 x 0.5 / 16) x 100 = 24.5pp |
| first card only, 4 cards | 50 | 13.9 | 1.96 x sqrt(0.5 x 0.5 / 50) x 100 = 13.9pp |

| cell | n | margin pp |
|---|---|---|
| 19-39_m | 70 | 11.7 |
| 19-39_f | 70 | 11.7 |
| 40-59_m | 15 | 25.3 |
| 40-59_f | 15 | 25.3 |
| 60+_m | 15 | 25.3 |
| 60+_f | 15 | 25.3 |

Design effect = 1 + (m - 1) x ICC. ICC values are from the KREI data of this project.

| item | m | ICC | design effect | effective n | margin pp | arithmetic |
|---|---|---|---|---|---|---|
| weekly | 5 | 0.5 | 3.0 | 66.7 | 12.0 | 1 + (5 - 1) x 0.5 = 3.0; 200 / 3.0 = 66.7; 1.96 x sqrt(0.5 x 0.5 / 66.7) x 100 = 12.0pp |
| ever | 5 | 0.41 | 2.64 | 75.8 | 11.3 | 1 + (5 - 1) x 0.41 = 2.64; 200 / 2.64 = 75.8; 1.96 x sqrt(0.5 x 0.5 / 75.8) x 100 = 11.3pp |
| carb | 5 | 0.1 | 1.4 | 142.9 | 8.2 | 1 + (5 - 1) x 0.1 = 1.4; 200 / 1.4 = 142.9; 1.96 x sqrt(0.5 x 0.5 / 142.9) x 100 = 8.2pp |

Cards proposed for the real sample:

- A: 패널 순서를 쓸 수 없어 담당자 선택이 필요한 후보
- B: 패널 순서를 쓸 수 없어 담당자 선택이 필요한 후보
- C: 패널 순서를 쓸 수 없어 담당자 선택이 필요한 후보
- 기존 제품 기준 카드가 이 시연에는 없습니다. 담당자가 넣어야 합니다.

Weight the sample to read a national value. The target and rest split is a design choice, not a population share.
This plan answers whether a large gap has the right direction and where the panel is wrong. It does not measure 12 cells.

## questionnaire

문항은 패널과 같은 문구입니다. 답을 본 뒤 문항을 추가하지 않습니다. 시스템은 설문을 보내지 않으며 발주는 조사 담당자가 합니다.

앵커 문항은 공개 기준과 같은 문구로 표본 치우침을 점검합니다.

- concept_A (concept)
- concept_B (concept)
- concept_C (concept)
- anchor_a19 (anchor)
- anchor_a15 (anchor)
- demo_연령대 (demographic)
- demo_성별 (demographic)
- demo_거주 지역 (demographic)
- demo_가구원 수 (demographic)

- 가구당 1명만 받습니다.
- 모집 채널과 면접원 식별값을 받고 유효 표본을 보고합니다.
- 초대 명단과 전원의 응답 여부를 받습니다. 받지 못하면 보고서에 「보정 불가, 직접 추정만」이라고 씁니다.
- 한 사람이 여러 장을 보므로 순서를 섞고 첫 카드 결과를 따로 봅니다.

## 실측 200명 회수 뒤의 규칙 (R1 요건)

- 실측 200명이 오면 그 200명만으로 나이·성별 단순 회귀(R1)를 적합하고, 같은 200명 안의 교차 검증으로 패널 보정값과 겨룹니다.
- 패널 보정값이 R1을 이기지 못하면(차이 구간이 전부 0 아래가 아니면) 패널 값을 이번 결정에서 뺍니다. 보고서에 그대로 적습니다.
- 이 규칙은 앞선 결과에서 왔습니다. 2단계에서 같은 200명 R1과 겨룬 12개 조합 중 통과한 것은 0개였습니다.
- 초대 명단이나 응답 여부를 받지 못하면 「보정 불가, 직접 추정만」으로 씁니다.
- 구현은 src/lotte_audit/agent/compare.py의 compare_panel_direct이고, 지금까지는 합성 실측 답으로만 시험했습니다. 실제 실측 답으로 돌린 적은 없습니다.

## approval and cost

Approved by: stage brief, no person at the keyboard at 2026-11-01T16:33:52+00:00, plan 36e6fe64e3672a3f90ccac7396d19cd89c1d79b8a04888d1c68a60d6437b1645.

이 승인은 사람이 키보드에서 한 것이 아니라 작업 지시서의 예산 범위에 따른 시연 승인입니다.

Plan: 1850 calls, cost cap 2.1798 USD, formula 150 personas x 6 cards x 2 models, plus no-persona calls.

Cost: {"stage_panel_usd": 1.203768, "stage_agent_models_usd": 0.181954, "stage_total_usd": 1.385722, "stage_budget_usd": 5.0, "this_run_panel_usd": 0.0}
