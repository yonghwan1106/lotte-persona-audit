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

자료 게시글에는 공공누리 제4유형(출처표시, 상업적 이용금지, 변경금지) 표시가 붙어 있습니다. 같은 표시가 공지사항과 문의 게시글에도 붙어 있어, 자료별로 정한 것인지 게시판 기본값인지는 확인하지 못했습니다. 원자료와 응답자 단위 파생본은 재배포하지 않습니다. 이 저장소에는 재현 스크립트와 집계만 둡니다.

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

평가 도구(`audit.py`)는 API를 부르지 않습니다. API를 부르는 코드는 `src/panel_run.py`뿐입니다. 응답자 코드 하나당 호출 한 번이고, 코드는 모델에 보이지 않습니다. 모델, 가격, 설정, 프롬프트 해시는 `config/gate_run.json`에, 프롬프트는 `config/gate_prompt.json`에 고정돼 있습니다. API 키는 실행할 때 저장소 밖 파일에서 읽습니다. 답, 캐시, 호출 기록은 `runs/` 아래에 두며 커밋하지 않습니다.

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

총비용이 관문 전체 20달러에 닿기 전에 멈춥니다. 잔액 없음(429 insufficient_quota)이면 재시도 없이 바로 멈춥니다.

## 사전 등록

`config/prereg.json`이 조건, 지표, 전환 규칙, 재현 패턴 정의를 담습니다. `manifests/frozen.json`이 설정 파일 해시를 담고, 설정이 바뀌면 채점이 멈춥니다. 답을 본 뒤에는 바꾸지 않습니다.

## 구조

| 경로 | 내용 |
|---|---|
| `audit.py` | 명령줄 진입점 |
| `src/lotte_audit/` | 파이썬 코드, ASCII 전용 |
| `config/` | 한국어 문구, 누출 정규식, 허용 목록, 사전 등록 |
| `manifests/` | 분할 목록(행 번호, 행 해시, 분할), 설정 해시 |
| `results/` | 집계 결과만 |
| `runs/` | 페르소나 배치, 열쇠, 답. 커밋 제외 |
| `tests/` | pytest |

## 분할

조사 단위(vuid)를 표본층(STR) 안에서 통째로 한 분할에 넣습니다. 시드 42, 학습 약 50%, 보정 후보 약 10%, 시험 약 40%입니다. 같은 가구와 같은 조사 단위는 분할을 넘나들지 않습니다.
