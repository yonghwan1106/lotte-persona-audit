import type { Metadata } from "next";
import { Caveats } from "@/components/Notes";
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
  { key: "spend.stage4", label: "4단계 (에이전트 모델과 탐색, 새 패널 호출 없음)" },
  { key: "spend.all_stages_including_attacks", label: "합계" },
];

export default function ReproPage() {
  return (
    <>
      <h1>재현과 자료</h1>
      <p className="lead">채점과 규칙 비교에는 API 키가 필요 없습니다. 답을 새로 만드는 단계만 키와 비용이 듭니다. 원자료는 직접 받아야 합니다.</p>

      <h2>자료 출처와 이용 조건</h2>
      <div className="band">
        <p>
          <strong>출처:</strong> 한국농촌경제연구원, 식품소비행태조사 원시자료 2023~2025,{" "}
          <a href="https://krei.re.kr/foodSurvey/page/460" rel="noreferrer">
            https://krei.re.kr/foodSurvey/page/460
          </a>
        </p>
        <p>
          <strong>공공누리 제4유형(출처표시, 상업적 이용금지, 변경금지).</strong> 자료 게시글에 이 표시가 붙어 있습니다. 같은 표시가 공지사항과 문의 게시글에도 붙어 있어, 자료별로 정한 것인지 게시판 기본값인지는 확인하지 못했습니다.
        </p>
        <p>이 사이트에는 집계값만 있습니다. 원자료와 응답자 단위 파생본은 재배포하지 않습니다. 「2024 원자료 집계」는 공개 원자료를 직접 집계한 값이고 공표 통계와 대조하지 않았습니다.</p>
      </div>
      <p>
        <strong>롯데 자료를 쓰지 않았습니다.</strong> 롯데칠성음료 등 그룹사의 내부 자료, 판매 자료, 조사 자료는 어디에도 들어 있지 않습니다. 이 사이트는 롯데와 제휴 관계가 없습니다. 시연 카드는 모두 가상입니다.
      </p>

      <h2>저장소에 없는 것</h2>
      <ul>
        <li>KREI 원자료(<code>data/raw/</code>)와 행 단위 파생 파일(<code>data/derived/</code>)</li>
        <li>페르소나 문장, 패널 답, 응답자 코드, 호출 기록(<code>runs/</code>)</li>
        <li>API 키. 저장소 밖 파일에서 실행할 때 읽습니다.</li>
      </ul>
      <p className="small">
        작업 브랜치 <code>gate-run</code>에는 분할 목록 <code>manifests/splits_seed42.csv</code>(응답자 전원의 행 번호, 행 해시, 분할)가 이력째 남아 있어 공개하지 않습니다. 공개용은 그 파일과 실제 응답자 코드를 전체 이력에서 뺀 로컬 브랜치 <code>public</code>이고, 분할은 시드로 다시 만들어 전체 해시로 대조합니다. 이 사이트의 코드(<code>web/</code>)도 <code>public</code>에만 커밋합니다. 아직 원격에 올리지 않았습니다.
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
.venv/Scripts/python.exe src/stage4_run.py demo-start --run-id demo7
.venv/Scripts/python.exe src/stage4_run.py demo-resume --run-id demo7 --approver "이름"
.venv/Scripts/python.exe src/stage4_run.py make-standin --name krei_draw0
.venv/Scripts/python.exe src/stage4_run.py ingest-real --run-id demo7 --real 파일 --panel 파일 --source-label "라벨" --approver "이름"`}</pre>
      <h3>수치 시트와 이 사이트</h3>
      <pre>{`.venv/Scripts/python.exe src/make_numbers_sheet.py --record-tests  # results/numbers_sheet.json
python web/scripts/build_data.py                                   # 집계만 web/data로 복사, 누출 점검
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
      <Caveats items={caveats(["spend.gate", "spend.wf7_attacks", "tests.passed"])} />

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
    </>
  );
}
