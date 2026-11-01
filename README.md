# lotte-persona-audit

소비자 패널 감사기의 평가 도구입니다. LLM 페르소나가 실제 한국인 응답자의 숨긴 답을 얼마나 재현하는지 잽니다. 채점에는 LLM 호출이 없고 API 키도 필요 없습니다. 답을 만드는 단계는 아래 「관문 실행」에 있습니다.

대상은 기존 음료 행동의 재현입니다. 신제품 성패는 재지 않습니다.

## 자료

KREI 식품소비행태조사 성인 가구원 파일입니다. `data/raw/`에 직접 받아 둡니다. 이 폴더와 행 단위 파생 파일은 커밋하지 않습니다.

| 파일 | 내용 | 받는 곳 |
|---|---|---|
| `a2025.sav` | 2025 성인 5,874행, 가중치 psfwt | https://krei.re.kr/foodSurvey/board/atchDown.do?no=113677 (zip 안의 성인 가구원 파일) |
| `a2024.sav` | 2024 성인 5,851행 | https://krei.re.kr/foodSurvey/board/atchDown.do?no=111060 |
| `a2023.sav` | 2023 성인 5,811행 | https://krei.re.kr/foodSurvey/board/atchDown.do?no=111049 |
| `questionnaire_adult_2025.pdf` | 2025 성인 설문지 | https://krei.re.kr/foodSurvey/board/atchDown.do?no=113682 |

## 재사용 조건

자료 게시글에는 공공누리 제4유형(출처표시, 상업적 이용금지, 변경금지) 표시가 붙어 있습니다. 같은 표시가 공지사항과 문의 게시글에도 붙어 있어, 자료별로 정한 것인지 게시판 기본값인지는 확인하지 못했습니다. 원자료와 응답자 단위 파생본은 재배포하지 않습니다. 작업 브랜치 `gate-run`에는 분할 목록 `manifests/splits_seed42.csv`(응답자 전원의 행 번호, 행 해시, 분할)가 이력째 남아 있으므로 공개하지 않습니다. 공개용은 그 파일과 실제 응답자 코드를 전체 이력에서 뺀 로컬 브랜치 `public`이며, 분할은 시드로 다시 만들어 전체 해시로 대조합니다.

출처: 한국농촌경제연구원, 식품소비행태조사 원시자료 2023~2025, https://krei.re.kr/foodSurvey/page/460

## 실행 순서

작업 폴더와 무관하게 절대 경로로 실행할 수 있습니다.

```
python audit.py prepare          # 표적 확인, 분할 목록 작성
python audit.py reproduce        # 스카우트와 비교 작업 수치의 전체 파일 재현
python audit.py hunt             # 학습 분할 안에서 주 1회 AUC 0.89~0.912의 원인 조사
python audit.py screen           # 학습 분할 누출 선별, config/allowlist_final.json 작성
python audit.py baselines        # 시험 분할 기준선
python audit.py batches          # 관문 패널 입력 배치와 정답 열쇠(커밋 제외)
python audit.py gate-reference   # 같은 300명의 바닥 값과 실제 답 기준값
python audit.py freeze           # 사전 등록 설정의 해시 고정
python audit.py score            # runs/gate/answers/*.csv 채점
python -m pytest tests -q
```

## 채점 입력

`runs/gate/answers/`에 CSV를 둡니다. 파일 이름은 자유이고 열쇠가 코드별 조건을 알려 줍니다.

```
code,p_zero_ever,p_zero_weekly,p_carb_top1
XXXXXXXX,0.42,0.08,0.05
```

값은 0 이상 1 이하의 확률입니다. C0, C1, C2의 모든 코드가 한 번씩 있어야 합니다. 빠진 코드, 모르는 코드, 중복, 범위 밖 값이 있으면 멈춥니다. 다른 답 폴더는 `--answers`, 결과 폴더는 `--out`으로 지정합니다.

결과는 `results/gate_score.json`과 `results/gate_score.md`에 쓰고, 마지막 줄에 `SWITCH` 또는 `NO SWITCH`를 출력합니다.

## 관문 실행

평가 도구(`audit.py`)는 API를 부르지 않습니다. 관문에서 API를 부르는 코드는 `src/panel_run.py`뿐입니다. 응답자 코드 하나당 호출 한 번이고, 코드는 모델에 보이지 않습니다. 모델, 가격, 설정, 프롬프트 해시는 `config/gate_run.json`에, 프롬프트는 `config/gate_prompt.json`에 고정돼 있습니다. API 키는 실행할 때 저장소 밖 파일에서 읽습니다. 답, 캐시, 호출 기록은 `runs/` 아래에 두며 커밋하지 않습니다.

```
python src/panel_run.py check                       # 고정 설정 확인, 호출 없음
python src/panel_run.py smoke                       # 주 모델 C1 3건, C2 3건, 전체 비용 추정(results/gate_smoke.json)
python src/panel_run.py run --model gpt-6.1-terra   # 전체 700코드, 캐시된 코드는 다시 호출하지 않음
python src/panel_run.py run --model gpt-6-luna
python audit.py score --answers runs/gate/answers_gpt-6.1-terra --out results/gate --name gate_score_gpt-6.1-terra
python audit.py score --answers runs/gate/answers_gpt-6-luna --out results/gate --name gate_score_gpt-6-luna
python src/gate_explore.py --answers runs/gate/answers_gpt-6.1-terra --out results/gate --name gate_explore_gpt-6.1-terra   # 탐색용, 규칙과 무관
python src/panel_run.py status --write              # 집계 비용(results/gate_run_summary.json)
```

총비용이 관문 전체 8달러에 닿기 전에 멈춥니다. 잔액 없음(429 insufficient_quota)이면 재시도 없이 바로 멈춥니다.

## 본실행

질문은 하나입니다. 합성 패널에 실제 응답자 약 200명을 더한 것이 그 200명만 쓴 것을 이기는가. 계획은 `config/prereg_main.json`, 실행 설정은 `config/main_run.json`에 있고, 프롬프트와 요청 설정은 관문과 같습니다. 예산은 이 단계만 6달러이고 호출 기록은 `runs/main/logs/calls.jsonl`에 따로 남습니다. `manifests/frozen_main.json`이 설정, 코드, 패널의 해시를 담습니다. 해시가 다르면 실행과 채점이 멈추고, 커밋 전이면 실행이 멈춥니다. 2단계 채점은 커밋 여부를 보지 않으며, 그 확인은 3단계부터 채점에도 들어갑니다.

```
python src/main_run.py prepare        # 시험 패널 1,000명으로 확장, 보정 패널 632명, 호출 없음
python src/main_run.py freeze         # 해시 고정, 이후 커밋
python src/main_run.py check          # 고정 확인, 관문 재사용 수, 예상 비용, 호출 없음
python src/main_run.py run            # Terra C2, Terra C1, Luna C2, Luna C1, 안정성 순서
python src/main_run.py status --write # results/main/main_run_summary.json
python src/main_run.py score          # results/main/main_score.json, main_score.md
```

신뢰 지도 규칙은 `src/lotte_audit/verdict.py`, 추정기는 `src/lotte_audit/calibration.py`에 있습니다. 패널 원수치는 시장 수치로 쓰지 않습니다. 결과에는 집계만 남고, 응답자 코드와 페르소나 문장은 `runs/main/` 밖으로 나가지 않습니다.

## 3단계

2단계에서 패널 + 실제 200명은 평평한 수축(E2)은 이겼지만 같은 200명의 나이·성별 회귀(R1)는 이기지 못했습니다. 규칙 v1은 LLM이 아닌 대체 패널도 12개 중 11개를 통과시켰습니다. 3단계는 두 부분입니다. 계획은 `config/prereg_stage3.json`, 실행 설정은 `config/stage3_run.json`, 프롬프트는 `config/stage3_prompt.json`에 있고, `manifests/frozen_stage3.json`이 해시를 담습니다. 커밋 전이거나 해시가 다르면 호출, 판정, 채점이 모두 멈춥니다.

```
python src/stage3_run.py prepare        # 관문 300명, C1과 C2, 호출 없음
python src/stage3_run.py screen         # 학습 분할에서 C2 허용 목록을 각 보기와 대조, 호출 없음
python src/stage3_run.py freeze         # 해시 고정, 이후 커밋
python src/stage3_run.py check          # 고정 확인, 호출 없음
python src/stage3_run.py verdict        # 1부: 규칙 v1과 v2 비교, 저장된 2단계 답과 대체 패널, 호출 없음
python src/stage3_run.py smoke          # 2부: C2 3건, C1 3건, 비용 추정
python src/stage3_run.py run            # 2부: 600건, 이 단계 예산 3달러
python src/stage3_run.py status --write # results/stage3/stage3_run_summary.json
python src/stage3_run.py score          # 2부: results/stage3/option_ranking.json, option_ranking.md
```

1부의 규칙 v2(`src/lotte_audit/verdict_v2.py`)는 **2단계 답을 본 뒤에 썼으므로 그 답에 대해서는 사전 등록이 아닙니다.** v1(`verdict.py`)은 바꾸지 않았고 나란히 보여 줍니다. v1의 `level_trusted`는 E2를 이겼다는 뜻일 뿐이어서 v2 출력과 비교 표에서는 `beats_e2`로 부릅니다. 2부는 A15 보기 순서를 패널이 맞추는지 재며, 이 프롬프트의 답을 보기 전에 고정했습니다. 신제품은 재지 않습니다. 결과에는 집계만 남고, 호출 기록과 답은 `runs/stage3/` 밖으로 나가지 않습니다.

결과는 `results/stage3/`에 있습니다. v2의 「보정 후 참고」는 LLM 답, 대체 패널, 실제 답을 일부 알려 준 양성 대조(AUC 1.0 포함) 어디에서도 나오지 않았고, 응답자 본인의 실제 답을 그대로 넣은 패널에서도 나오지 않습니다(`results/verdict_v3/`). 따라서 이 라벨이 나오지 않은 것을 LLM의 실패 증거로 읽으면 안 됩니다. carb의 실측 전용은 패널 밖 truth에서 실측 기울기 구간이 0을 포함해 규칙으로 정해지며, 실제 답을 넣은 패널도 같은 라벨입니다.

순서 시험의 고정 판정은 어느 간격 구간에서도 패널이 실제 200명이나 2024년 값을 넘지 못했다는 것입니다. 다만 truth와 똑같은 추정치도 3~5pp와 5pp 이상 구간에서 이 판정을 넘지 못하므로(`results/verdict_v3/ceiling.json`) 이 규칙은 변별 근거가 아닙니다. 근거는 쌍 정확도 차이입니다. 「2024년 값」은 2024 공개 원자료를 직접 집계한 값이고 공표 통계와 대조하지 않았습니다.

`results/main/main_score.md`에는 v1의 level trusted 열이 남아 있습니다. 동결 산출물이므로 고치지 않으며, 인용하지 않습니다.

## 규칙 v3

`src/lotte_audit/verdict_v3.py`, 실행은 `src/verdict_v3_run.py`(`acceptance`, `apply`, `ceiling`)입니다. API 호출이 없습니다. **v3는 답을 다 본 뒤 공개적으로 쓴 규칙이고 사전 등록이 아닙니다.** v1과 v2는 그대로입니다.

- 보정 후 참고: 보정 추정기가 패널 밖 truth에서 R1을 이김. row 추출 구간이 0을 제외하고 cluster 추출 평균이 같은 방향.
- 판정 불가: 위가 아니고 실측 기울기 구간이 0을 포함.
- 방향만, 실측 전용: 그 밖에는 v1의 세 방향 점검으로 나눔.
- 성별 차이 사용 금지 플래그는 따로이고, 구간 경계에 있어 시드에 따라 수가 변합니다.

LLM 답에 적용하기 전에 대조군 합격선을 먼저 쟀습니다(규칙과 합격선을 커밋한 뒤 계산). 실제 답 대조군은 4칸 각각 3항목 중 2개 이상, LLM이 아닌 대체 패널은 12개 중 1개 이하가 합격선이고, 결과는 합격입니다(세 시드). 실제 답 대조군의 4칸은 답이 같아 한 결과를 네 번 본 것입니다. 합격했어도 첫 분기는 여전히 실제 답에 가까운 패널에서만 작동합니다. 일부 답을 알려 준 대조에서는 가장 강한 강도에서만 나옵니다. 그래서 어떤 v3 라벨도 제품 라벨로 쓰지 않습니다. LLM 답은 12개 중 보정 후 참고 0개입니다. v1, v2, v3의 나란한 표는 `results/verdict_v3/verdict_v3.md`에 있습니다.

감사 에이전트의 판정은 동결된 v2 위에서 그대로 돌아갑니다. v3로 바꾸지 않았습니다.

## 감사 에이전트

콘셉트 카드를 받아 패널을 돌리고 칸별 판정, 실측 200명 배분, 문항지, 원장 기록까지 내는 에이전트입니다. 신제품 성패를 예측하지 않습니다. 정답이 없는 실행이므로 판정은 실행 안의 잡음과 앞 단계의 규칙 v2에서 나옵니다. 구매 의향 값은 패널 내부 값이고 시장 수치나 판매 전망이 아닙니다.

에이전트는 둘입니다. 감사 매니저(`gpt-6.1-sol`)가 카드를 구조화하고 도구를 고르며, 서술 전문가(`gpt-6.1-terra`)는 매니저의 도구(`as_tool`)로만 돕니다. 접수 점검에는 고정 패턴과 Decisions API(`gpt-6-luna`)를 씁니다. OpenAI Agents SDK 0.24.0을 씁니다. 패널 응답기는 에이전트가 아니라 도구 없는 무상태 Responses 호출이며(`src/lotte_audit/agent/panel.py`), 응답자 코드는 모델에 보이지 않습니다.

SDK는 openai 3.x를 요구해 이 저장소의 venv에만 설치합니다.

```
python -m venv --system-site-packages .venv
.venv/Scripts/python.exe -m pip install "openai-agents==0.24.0"
```

```
.venv/Scripts/python.exe src/agent_run.py smoke        # 시연 밖 카드로 모델당 3건, 토큰과 비용만
.venv/Scripts/python.exe src/agent_run.py freeze       # 프롬프트 해시 기록, 고정 파일 해시, 이후 커밋
.venv/Scripts/python.exe src/agent_run.py check        # 고정 확인, 호출 없음
.venv/Scripts/python.exe src/agent_run.py demo-start --run-id demo5   # 검증과 계획까지, 승인 대기에서 멈추고 실행 상태를 저장
.venv/Scripts/python.exe src/agent_run.py demo-resume --run-id demo5 --approver "이름"   # 저장한 실행을 승인하고 같은 실행으로 이어 감
.venv/Scripts/python.exe src/agent_run.py card-confirm --run-id demo5 --card ID --decision remove --approver "이름"   # 사실형 유도 문장에 대한 사람의 결정
.venv/Scripts/python.exe src/agent_run.py scenarios --runs 3 --demo-run demo5 --probe    # 행동 시나리오, 실제 API
.venv/Scripts/python.exe src/agent_run.py status --write                   # results/agent/run_summary.json
.venv/Scripts/python.exe -m pytest tests -q
```

이 단계 예산은 5달러이고 호출 전에 거부합니다. 도구 순서는 코드가 정합니다. 선행 조건이 없으면 도구가 `blocked`를 돌려주고 아무것도 하지 않습니다. `run_panel`은 SDK 승인(`needs_approval=True`)과 코드의 승인 기록을 모두 요구합니다. 승인은 계획 해시에 묶이고, 계획 해시는 카드별 정리된 문구, 앵커, 역할을 담습니다. 승인을 누가 했는지 코드는 확인하지 못합니다. 사람 승인 화면은 없고 CLI 인자뿐이며, 시연 승인도 사람이 하지 않았습니다.

임계값이나 라벨을 인자로 받는 도구는 없습니다. 다만 카드의 `anchor_items`가 칸 라벨을 정합니다. 그래서 등록 카드의 앵커는 동결 파일에 있고, 미등록 카드에서 앵커를 줄이면 보고서와 원장에 표시합니다. 실행 기록이 생긴 뒤에는 `validate_card`가 막히므로 같은 답에 앵커를 바꿔 다시 판정할 수 없습니다. 앵커가 다른 카드끼리의 라벨 차이는 안의 차이가 아닙니다. 시연에서 A, B가 실측 전용이고 C가 방향만인 것은 carb 앵커 유무의 차이입니다.

카드 접수: 등록 카드는 `suspected_instructions`를 무시하므로 모델이 문구를 줄일 수 없습니다. 미등록 카드에서 모델이 지목할 때는 한 문장 전체만 제거됩니다. 사전 조사, 다수 구입, 소비자 반응 같은 사실형 유도 문장은 고정 패턴으로 잡아, 사람이 `card-confirm`으로 제거나 유지를 정하기 전에는 카드가 계획에 들어가지 못합니다. 모델이 정할 수 없습니다. 미등록 카드는 모델이 문구를 옮겨 적으므로, 모델이 문장을 바꿔 쓰면 패턴을 비켜 갈 수 있지만 대기 표시는 사람이 풀기 전까지 남습니다. 패턴은 시험한 형태만 잡습니다. 시험한 사실형 문장 중 잡히지 않은 것은 `results/fix_stage/attack_replay_offline.json`에 그대로 적었습니다. 그런 문장은 카드를 통과하며, 탐침에서 같은 부류의 문장은 패널 값을 크게 움직였습니다(`results/numbers_sheet.json`의 `attacks.wf7.probe`).

`plan_run`은 패널 수 300을 상한으로, 파일럿 수 100을 하한으로 둡니다. 동결 설정의 `max_personas` 1000은 그대로지만 코드가 더 낮은 상한을 씁니다. 매니저의 `complete`는 코드 상태로 확인합니다. 원장이 쓰이지 않았거나 사람 확인을 기다리는 카드가 있으면 `stopped`로 바꾸고, 주장한 값은 `claimed_status`에 남깁니다.

패널과 두 에이전트의 요청은 `store=False`로 보냅니다. API가 돌려준 값으로 False를 확인한 것은 에이전트 단계뿐이고, 관문, 본실행, 3단계 호출 로그에는 그 값이 없습니다. Decisions API에는 `store` 인자가 없습니다. 레퍼런스에 없고, 실제로 보내면 `400 unknown_parameter`입니다(`results/fix_stage/decisions_store_probe.json`). 사용자 요청 문장이 이 경로로 나갑니다. 문서의 데이터 표는 이 끝점의 애플리케이션 상태 보관을 없음으로 적고 있고 남용 감시 로그는 최대 30일로 적고 있는데, 이 저장소에서 직접 확인한 것은 아닙니다. SDK 트레이싱은 설정으로 끄며 네트워크를 관찰해 확인하지는 않았습니다. 호출 기록은 `runs/agent/logs/`에 있습니다.

서술 전문가의 출력은 `{{m:지표id}}` 자리표시만 숫자를 담을 수 있습니다. 코드 규칙(`config/agent_text.json`의 `narration_guard`와 `narration.py`)은 자리표시 밖의 아라비아 숫자와 유니코드 숫자값을 가진 문자(한자 수사, 위첨자, 분수 기호 포함), 수십·수백, 붙여 쓴 한글 수사, 「점」 소수, 분수, 영어 수사, 그리고 나열된 시장 표현과 맛 표현을 기각합니다. 없는 지표 id도 기각합니다. 같은 규칙이 매니저 note에도 적용되어, 걸리면 note를 버립니다. 규칙은 나열된 형태만 잡으므로 다르게 쓴 수량 표현은 통과할 수 있습니다. 판정 문장은 코드 템플릿이고, 서술 문장에는 「가설:」이 자동으로 붙습니다. 패널 이유는 낱말 빈도만 결과에 남기고 가설로 표시합니다.

결과는 `results/agent/`에 있습니다. 최종 시연은 `demo5/`이고 `report.md`의 첫 줄이 매니페스트 해시, `transcript.jsonl`이 도구 호출 기록입니다. 패널 호출은 첫 실행 `demo/`에서만 일어났고, `demo2`~`demo5`는 서술과 기록을 고친 뒤 같은 캐시로 다시 돈 것입니다. 행동 시나리오는 `scenarios/results.md`에, 고치기 전의 실패 기록은 `scenarios/first_batch/`와 `dev_runs/`에 남겨 두었습니다. 시연 카드는 모두 가상이며 정답이 없습니다. 추적되는 `demo`~`demo5`의 `diagnostics.json`에는 숨긴 칸의 T2B 값이 그대로 있어, 그 실행들에서 「절대값 숨김」은 보고서 본문에만 해당합니다. 고친 뒤의 실행(`results/fix_stage/demo6/`)은 추적 파일에 절대값을 싣지 않고 쌍 차이만 남기며, 전체 값은 `runs/` 아래 저장 상태에만 있습니다.

실측 경로는 만들지 않았습니다. 있는 것은 함수 `compare_panel_direct`(실측 200명의 단순 회귀를 패널이 못 이기면 패널 값을 뺌)뿐이고, 합성 실측 답으로만 시험했습니다. 실측 답을 받는 경로, 응답자별 패널 값을 만드는 경로, 결과를 보고서에 적는 코드는 없습니다. 원장의 `human_decision`, `real_results`, `launched`, `pos`는 항상 null입니다.

`config/agent_text.json`(거절 패턴, 숫자 규칙, 매니저 지시)은 동결 대상이 아니고 매니페스트 해시로만 추적합니다. 이 단계의 시나리오 통과는 시험한 형태에서 조합당 3회의 결과이며 일반 방어의 증거가 아닙니다.

## 수정 단계

위 규칙을 고친 뒤 시나리오와 시연을 다시 돌린 단계입니다. 실행기는 `src/agent_fix_run.py`, 설정은 `config/fix_stage.json`이고, 호출 기록은 `runs/agent_fix/logs/`, 결과는 `results/fix_stage/`, 예산은 따로 3달러입니다. 패널 답은 앞 단계 캐시만 읽고 새 패널 호출은 코드가 막습니다. 앞 단계의 파일은 건드리지 않습니다.

```
.venv/Scripts/python.exe src/agent_fix_run.py check
.venv/Scripts/python.exe src/agent_fix_run.py demo-start --run-id demo6
.venv/Scripts/python.exe src/agent_fix_run.py demo-resume --run-id demo6 --approver "이름"
.venv/Scripts/python.exe src/agent_fix_run.py scenarios --runs 3 --demo-run demo6
.venv/Scripts/python.exe src/agent_fix_run.py attacks --demo-run demo6            # wf7에서 뚫린 공격, 실제 API
.venv/Scripts/python.exe src/agent_fix_run.py attacks-offline --demo-run demo6    # 호출 없음
.venv/Scripts/python.exe src/agent_fix_run.py status --write
.venv/Scripts/python.exe src/make_numbers_sheet.py --record-tests                 # results/numbers_sheet.json
```

결과물에 인용할 수 있는 수치는 `results/numbers_sheet.json`에 모았습니다. 스크립트가 결과 파일에서 읽어 만들며, 항목마다 값, 단위, 출처, 단계, 주의 문구가 있습니다.

## 사전 등록

`config/prereg.json`이 조건, 지표, 전환 규칙, 재현 패턴 정의를 담습니다. `manifests/frozen.json`이 설정 파일 해시를 담고, 설정이 바뀌면 채점이 멈춥니다. 답을 본 뒤에는 바꾸지 않습니다.

## 구조

| 경로 | 내용 |
|---|---|
| `audit.py` | 명령줄 진입점 |
| `src/lotte_audit/` | 파이썬 코드, ASCII 전용 |
| `src/lotte_audit/agent/` | 감사 에이전트, 도구, 진단, 판정, 배분, 숫자 규칙 |
| `src/agent_run.py` | 감사 에이전트 실행기 |
| `src/agent_fix_run.py` | 수정 단계 실행기 |
| `src/verdict_v3_run.py` | 규칙 v3와 대조군, API 호출 없음 |
| `src/make_numbers_sheet.py` | 수치 시트 생성 |
| `config/` | 한국어 문구, 누출 정규식, 허용 목록, 사전 등록 |
| `manifests/` | 분할 목록(행 번호, 행 해시, 분할. 이 브랜치에만 있음, 공개 금지), 설정 해시 |
| `results/` | 집계 결과. `numbers_sheet.json`은 인용 수치, `verdict_v3/`는 규칙 비교, `fix_stage/`는 수정 단계 |
| `runs/` | 페르소나 배치, 열쇠, 답. 커밋 제외 |
| `tests/` | pytest |

## 분할

조사 단위(vuid)를 표본층(STR) 안에서 통째로 한 분할에 넣습니다. 시드 42, 학습 약 50%, 보정 후보 약 10%, 시험 약 40%입니다. 같은 가구와 같은 조사 단위는 분할을 넘나들지 않습니다.
