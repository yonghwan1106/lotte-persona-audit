import type { Metadata } from "next";
import { Caveats } from "@/components/Notes";
import { Scene } from "@/components/viz/Scene";
import provenance from "@/data/provenance.json";
import { caveats, num, sheetEntries, usd } from "@/lib/numbers";

export const metadata: Metadata = { title: "재현과 자료 · 합성 패널 감사 기록" };

const SPEND = [
  { key: "spend.gate", label: "관문" },
  { key: "spend.stage2", label: "2단계 본실행" },
  { key: "spend.stage3", label: "3단계" },
  { key: "spend.agent_stage", label: "감사 에이전트 단계" },
  { key: "spend.wf7_attacks", label: "실제 API 공격, 저장소 원장 밖" },
  { key: "spend.fix_stage", label: "수정 단계" },
  { key: "spend.stage4", label: "4단계, 사람 승인 실행 전 (에이전트 모델, 탐색, 시나리오, 새 패널 호출 없음)" },
  { key: "spend.all_stages_including_attacks", label: "합계, 사람 승인 실행 전" },
  { key: "spend.stage4.human2.run", label: "사람 승인 실행 human2 (패널과 탐색, 캐시에 없던 답만 호출)" },
  { key: "spend.all_stages_through_human2", label: "합계, human2까지" },
];

export default function ReproPage() {
  return (
    <>
      <Scene className="page-head">
        <h1>재현과 자료</h1>
        <p className="lead">채점과 규칙 비교에는 API 키가 필요 없습니다. 답을 새로 만드는 단계만 키와 비용이 듭니다. 원자료는 직접 받아야 합니다.</p>
        <ol className="pipeline" aria-label="자료가 이 사이트까지 오는 길. 앞의 세 단계는 저장소 밖에 있고, 뒤의 세 단계는 공개 저장소에 있습니다.">
          <li className="is-out">
            <span>KREI 원자료, 직접 받기</span>
          </li>
          <li className="is-out">
            <span>분할과 페르소나, 저장소 밖</span>
          </li>
          <li className="is-out">
            <span>패널 답과 호출 기록, 저장소 밖</span>
          </li>
          <li>
            <span>집계와 채점 결과</span>
          </li>
          <li>
            <span>수치 시트</span>
          </li>
          <li>
            <span>이 사이트</span>
          </li>
        </ol>
        <p className="small">테두리가 옅은 단계는 공개 저장소에 없습니다. 행 단위 자료는 이 사이트로 오지 않습니다.</p>
      </Scene>
      <Scene tone="glass">
        <div className="plain">
      <h2>자료 출처와 이용 조건</h2>
      <div className="band">
        <p>
          <strong>인용:</strong> 한국농촌경제연구원, 식품소비행태조사 2025 원자료. 2023, 2024 원자료도 같은 조사의 것을 썼습니다. 받는 곳:{" "}
          <a href="https://krei.re.kr/foodSurvey/page/460" rel="noreferrer">
            https://krei.re.kr/foodSurvey/page/460
          </a>
        </p>
        <p>
          <strong>공공누리 제4유형(출처표시, 상업적 이용금지, 변경금지).</strong> 자료 게시글에 이 표시가 붙어 있습니다.
        </p>
        <p>
          <strong>KREI 학술정보팀 메일 회신(2026-11-02)의 요지</strong>
        </p>
        <ul>
          <li>연구원 홈페이지 등으로 공개하는 연구성과물에는 모두 공공누리 제4유형을 적용합니다.</li>
          <li>공개 원시자료의 응답 일부를 문장으로 바꿔 외부 AI 서비스(OpenAI API)에 입력해 활용하는 것은 가능합니다. 다만 AI 분석 결과는 연구자가 점검하고 확인해 활용해야 하고, 원자료가 한국농촌경제연구원의 식품소비행태조사 원자료임을 분명히 밝혀야 합니다. AI 분석 결과 등의 책임은 연구자에게 있습니다.</li>
          <li>이 경진대회 응모를 위해 연구원 자료를 쓰는 것은 상업적 이용에 해당하지 않는다고 판단한다는 회신입니다. 데이터 출처와 인용 표기는 정확해야 합니다.</li>
        </ul>
        <p>상업적 이용 판단은 이 응모에 대한 것입니다. 실제 서비스로 쓰려면 KREI와 별도로 협의하거나 자료를 바꿔야 합니다.</p>
        <p>이 사이트에는 집계값만 있습니다. 원자료와 응답자 단위 파생본은 재배포하지 않습니다. 「2024 원자료 집계」는 공개 원자료를 직접 집계한 값이고 공표 통계와 대조하지 않았습니다.</p>
      </div>
      <p>
        <strong>롯데 자료를 쓰지 않았습니다.</strong> 롯데칠성음료 등 그룹사의 내부 자료, 판매 자료, 조사 자료는 어디에도 들어 있지 않습니다. 이 사이트는 롯데와 제휴 관계가 없습니다. 시연 카드는 모두 가상입니다.
      </p>

      <h2 id="deployment">이 배포의 상태</h2>
      <ul>
        <li>
          <strong>실시간 접수 시험은 이 배포에서 꺼져 있습니다.</strong> 서버에 OPENAI_API_KEY를 올리지 않았습니다. 그래서 메뉴에 넣지 않았고, <code>/intake</code> 주소로 들어가면 안내문만 보입니다. 저장소를 받아 서버 환경 변수에 키를 넣으면 켜집니다.
        </li>
        <li>이 사이트의 다른 페이지는 저장된 집계를 보여 주며 모델을 호출하지 않습니다.</li>
      </ul>
      <p>
        코드와 집계: <a href="https://github.com/yonghwan1106/lotte-persona-audit" rel="noreferrer">github.com/yonghwan1106/lotte-persona-audit</a>
      </p>

      <h2>저장소에 없는 것</h2>
      <ul>
        <li>KREI 원자료(<code>data/raw/</code>)와 행 단위 파생 파일(<code>data/derived/</code>)</li>
        <li>페르소나 문장, 패널 답, 응답자 코드, 호출 기록(<code>runs/</code>)</li>
        <li>API 키. 저장소 밖 파일에서 실행할 때 읽습니다.</li>
      </ul>
      <p className="small">
        작업 브랜치 <code>gate-run</code>에는 분할 목록 <code>manifests/splits_seed42.csv</code>(응답자 전원의 행 번호, 행 해시, 분할)가 이력째 남아 있어 공개하지 않습니다. 공개용은 그 파일과 실제 응답자 코드를 전체 이력에서 뺀 브랜치 <code>public</code>이고, 분할은 시드로 다시 만들어 전체 해시로 대조합니다. 이 사이트의 코드(<code>web/</code>)도 <code>public</code>에만 커밋합니다.
      </p>

      <h2>재현 방법</h2>
      <p>KREI 성인 가구원 파일(<code>a2023.sav</code>, <code>a2024.sav</code>, <code>a2025.sav</code>)과 2025 설문지를 <code>data/raw/</code>에 받아 둡니다.</p>
      <h3>호출 없음: 분할, 기준선, 채점, 규칙 비교</h3>
      <pre>{`python audit.py prepare        # 표적 확인, 분할 목록 작성
python audit.py screen         # 학습 분할 누출 선별, 허용 목록 작성
python audit.py baselines      # 시험 분할 기준선
python audit.py batches        # 패널 입력 배치와 정답 열쇠(커밋 제외)
python audit.py score          # 답 CSV 채점
python src/main_run.py check   # 2단계 고정 확인
python src/stage3_run.py check # 3단계 고정 확인
python src/verdict_v3_run.py acceptance
python src/verdict_v3_run.py apply
python src/verdict_v3_run.py ceiling
python src/stage4_measures.py check       # 4단계 고정 확인
python src/stage4_measures.py allocation  # 패널이 200명 배분을 돕는가
python src/stage4_measures.py flags       # 실측 전에 틀린 칸을 지목하는가
python src/stage4_measures.py duel        # 정답 없는 대결이 규칙으로 쓸 만한가
python src/stage4_sensitivity.py          # 동결 결과를 본 뒤 돌린 시드 민감도
python src/stage4_posthoc.py              # 동결 결과를 본 뒤의 사후 계산: Terra C1, LLM 없는 floor, 조사 단위 온전 접힘, 접힘 시드 불안정
python src/stage4_run.py explore-scenarios # 탐색 필터에 합성 문장을 심는 시험
python -m pytest tests -q`}</pre>
      <h3>호출 있음: 답 생성 (키와 비용 필요, 단계별 예산에서 멈춤)</h3>
      <pre>{`python src/panel_run.py run --model gpt-6.1-terra
python src/panel_run.py run --model gpt-6-luna
python src/main_run.py run
python src/stage3_run.py run
.venv/Scripts/python.exe src/agent_run.py demo-start --run-id demo5
.venv/Scripts/python.exe src/agent_run.py demo-resume --run-id demo5 --approver "이름"
.venv/Scripts/python.exe src/agent_fix_run.py scenarios --runs 3 --demo-run demo6
.venv/Scripts/python.exe src/agent_fix_run.py attacks --demo-run demo6
.venv/Scripts/python.exe src/stage4_run.py demo-start --run-id demo8
.venv/Scripts/python.exe src/stage4_run.py demo-resume --run-id demo8 --approver "이름"
.venv/Scripts/python.exe src/stage4_run.py make-standin --name krei_draw0
.venv/Scripts/python.exe src/stage4_run.py ingest-real --run-id demo8 --real 파일 --panel 파일 --panel-model 모델 --panel-condition 조건 --source-label "라벨" --approver "이름"
.venv/Scripts/python.exe src/stage4_run.py scenarios --runs 1 --demo-run demo8
.venv/Scripts/python.exe src/stage4_run.py human-plan --run-id 새이름      # 계획만
.venv/Scripts/python.exe src/stage4_run.py human-approve --run-id 새이름   # 사람이 터미널에서 이름과 계획 해시를 입력`}</pre>
      <h3>수치 시트와 이 사이트</h3>
      <pre>{`.venv/Scripts/python.exe src/make_numbers_sheet.py --record-tests  # results/numbers_sheet.json
python web/scripts/build_data.py --ref public                      # 집계만 web/data로 복사, 누출 점검
cd web && npm install && npm run build && npm run start`}</pre>
      <p className="small">
        수치 시트는 {sheetEntries.toLocaleString("en-US")}개 항목이고 항목마다 값, 단위, 출처, 단계, 주의 문구가 있습니다. 오프라인 pytest는 {provenance.branch} 브랜치 기준 {num("tests.passed")}건 통과, 실패 {num("tests.failed")}건입니다.
      </p>

      <h2>비용</h2>
      <div className="table-wrap" tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th>단계</th>
              <th className="num">호출 로그 합계</th>
            </tr>
          </thead>
          <tbody>
            {SPEND.map((row) => (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td className="num">{usd(num(row.key))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Caveats items={caveats(["spend.gate", "spend.wf7_attacks", "spend.stage4", "spend.stage4.human2.run", "tests.passed"])} />

      <h2>이 사이트의 데이터 출처</h2>
      <p className="small">
        <code>web/scripts/build_data.py</code>가 커밋 <code>{provenance.commit.slice(0, 12)}</code>(브랜치 {provenance.branch})의 집계 파일에서 필드를 골라 복사했습니다. 응답자 코드와 페르소나 문장이 복사본과 빌드 결과에 없는지 같은 스크립트가 점검합니다. 페르소나 문장 점검은 문장 전체 일치 기준입니다.
      </p>
      <details>
        <summary>원본 파일과 SHA-256 보기</summary>
        <div className="table-wrap" tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th>파일</th>
                <th>SHA-256</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(provenance.files).map(([file, hash]) => (
                <tr key={file}>
                  <td>
                    <code>{file}</code>
                  </td>
                  <td>
                    <code>{hash}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
        </div>
      </Scene>
    </>
  );
}
