// Pieces of the stage 4 record shared by the first screen and the run page. Sentences come from the result files as written.
import demo from "@/data/demo.json";
import stage4 from "@/data/stage4.json";
import { any, bool, ciText, fixed, has, interval, num, signed, str } from "@/lib/numbers";

const DUEL_T = "stage4.duel.row.terra_C2.pooled.panel_excluded";

export const EXPLORE_SECTIONS = [
  { id: "objections", label: "반대 이유" },
  { id: "attractions", label: "끌리는 점" },
  { id: "segment_hypotheses", label: "세그먼트 가설" },
  { id: "survey_questions", label: "설문 문항 초안" },
] as const;

export const SEED_RUNS = ["fold_seed_99", "fold_seed_20261102", "draw_seed_99", "draw_seed_20261102"];

export function seedRunsFailed(): number {
  return SEED_RUNS.filter((r) => !bool(`stage4.duel.seed.${r}.acceptance_passed`)).length;
}

function pct(x: number, digits = 1): string {
  return (x * 100).toFixed(digits);
}

function cardSummary(id: string): string {
  const card = demo.cards.find((c) => c.id === id);
  if (!card) throw new Error(`no card ${id}`);
  return `${card.attributes.join(", ")}. ${card.price_band}`;
}

export function ActionTable() {
  return (
    <div className="table-wrap">
      <table className="stack action-table">
        <thead>
          <tr>
            <th style={{ width: "27%" }}>안</th>
            <th style={{ width: "14%" }}>제안</th>
            <th>이유</th>
          </tr>
        </thead>
        <tbody>
          {stage4.action.rows.map((row) => (
            <tr key={row.card}>
              <td>
                <strong>안 {row.card}</strong>
                <div className="small">{cardSummary(row.card)}</div>
              </td>
              <td data-label="제안">
                <span className="status">{str(`stage4.demo8.action.${row.card}`)}</span>
              </td>
              <td>{row.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function OrderNotes() {
  return (
    <>
      <ul>
        {stage4.action.order.map((line) => (
          <li key={line}>{line}</li>
        ))}
        <li>두 모델의 방향이 맞지 않거나 잡음 안에 있는 쌍은 적지 않았습니다: {stage4.action.order_hidden_pairs.join(", ")}.</li>
      </ul>
      <ul className="small">
        {[...stage4.action.order_notes, ...stage4.action.notes].map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </>
  );
}

export function DetectableTable() {
  const needed = [5, 10];
  return (
    <div className="table-wrap" tabIndex={0}>
      <table>
        <thead>
          <tr>
            <th className="num">실제 차이</th>
            <th className="num">두 안 나눠 보기, 안당</th>
            <th className="num">두 안 나눠 보기, 합계</th>
            <th className="num">한 사람이 둘 다, 상관 0</th>
            <th className="num">상관 0.3</th>
            <th className="num">상관 0.5</th>
          </tr>
        </thead>
        <tbody>
          {needed.map((gap) => {
            const base = `stage4.detectable.needed.gap_${gap}pp`;
            return (
              <tr key={gap}>
                <td>{gap}pp</td>
                <td className="num">{num(`${base}.between_per_arm`).toLocaleString("en-US")}명</td>
                <td className="num">{num(`${base}.between_total`).toLocaleString("en-US")}명</td>
                {["0.0", "0.3", "0.5"].map((rho) => (
                  <td className="num" key={rho}>
                    {num(`${base}.within.rho_${rho}`).toLocaleString("en-US")}명
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function ExploreCard({ card, only }: { card: "A" | "B" | "C"; only?: (typeof EXPLORE_SECTIONS)[number]["id"] }) {
  const doc = stage4.explore.cards[card];
  const sections = EXPLORE_SECTIONS.filter((s) => !only || s.id === only);
  return (
    <div>
      <div>
        <span className="card-id">안 {card}</span>
        <span className="role">{cardSummary(card)}</span>
      </div>
      {sections.map((section) => (
        <div key={section.id} className="explore-block">
          <div className="explore-head">{section.label}</div>
          <ul>
            {doc.sections[section.id].map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

/** The product decision on panel values, in the words of the report. Its facts come from config/panel_value_policy.json. */
export function HealthCheckDecision() {
  const policy = stage4.policy;
  const required: number | null = policy.consecutive_keeps_required;
  return (
    <div className="band">
      <p>
        <strong>실측 추정치로 쓰는 패널 값은 기본으로 보고서에서 뺍니다. 실제 200명과의 대결은 건강검진입니다.</strong> 실행마다 결과를 원장에 기록하고, 한 번의 keep은 패널 값을 보고서에 넣지 않습니다. 안별 제안의 쌍 차이는 실행 안의 진단이고 추정치가 아닙니다.
      </p>
      <p>패널 값은 조사 단위를 온전히 둔 접힘에서 프로젝트가 합의한 횟수만큼 연속 keep이 나온 뒤에만 넣을 수 있습니다. 합의한 횟수: {required === null ? "아직 합의하지 않음" : `${required}회`}. 그래서 지금은 어떤 보고서에도 들어가지 않습니다.</p>
      <p>
        이 결정은 동결 결과가 사전 기준을 통과한 것을 본 뒤({policy.decided_on})에 정한 사후 결정입니다. 동결 파일과 동결 수치는 바꾸지 않았고, 동결 라벨 <code>{policy.frozen_label}</code>은 기록으로 남기되 확정 판정으로 읽지 않습니다.
      </p>
    </div>
  );
}

export function HealthCheckReasons() {
  const same = "stage4.posthoc.same_sample";
  const intact = "stage4.posthoc.unit_intact.row";
  return (
    <ul>
      <li>
        같은 표본에서 접힘 시드만 바꿔도 결정이 뒤집힙니다. KREI 풀의 draw 0에서 Terra C2의 keep 비율은 접힘 시드 {num(`${same}.draw0.terra_C2.fold_seeds`)}개 기준 {pct(num(`${same}.draw0.terra_C2.pooled_keep_share`))}%이고, 200회 추출에 접힘 시드 {num(`${same}.all_draws.terra_C2.fold_seeds_per_draw`)}개씩 적용하면 {pct(num(`${same}.all_draws.terra_C2.share_draws_decision_changes`))}%의 추출에서 결정이 바뀝니다. 대체 패널도 {pct(num(`${same}.all_draws.surrogate_terra_slot.share_draws_decision_changes`))}%입니다.
      </li>
      <li>
        조사 단위를 온전히 둔 접힘의 row 추출 keep rate는 Terra C2 {num(`${intact}.terra_C2.keep_rate_mean`)}, 대체 패널 {num(`${intact}.surrogate_terra_slot.keep_rate_mean`)}, LLM 없는 floor {num(`${intact}.floor_no_llm.keep_rate_mean`)}, 양성 대조 {num(`${intact}.control_s1.0.keep_rate_mean`)}입니다(접힘 시드 {num(`${intact}.fold_seeds`)}개 평균). 이 접힘에서 Terra C2와 대체 패널은 구별되지 않습니다.
      </li>
      <li>
        시연 패널 조건은 C1입니다. Terra C1의 keep rate는 {num("stage4.posthoc.row.terra_C1.keep_rate")}이고, LLM 없는 나이·성별 floor는 {num("stage4.posthoc.row.floor_no_llm.keep_rate")}입니다. keep은 LLM 신호만으로 나오는 값이 아닙니다.
      </li>
    </ul>
  );
}

type StatusRow = { what: string; state: string; ok: boolean; scope: string };

function duelRows(): StatusRow[] {
  const real = stage4.real_results;
  const failed = seedRunsFailed();
  const health = real.health_check;
  const required: number | null = health.consecutive_keeps_required;
  const ingest = "stage4.demo8.ingest";
  return [
    {
      what: "실측 파일을 받아 규칙을 돌리고 보고서와 원장에 기록하는 경로",
      state: "만듦, 대용 자료로 실행",
      ok: true,
      scope: "CSV 두 개(실측 응답, 같은 응답자의 패널 값)를 받아 200명 안의 5겹 교차 검증으로 R1과 겨룹니다. 패널 모델과 조건을 함께 받아 원장에 남기고, unit_id 열이 있으면 조사 단위를 온전히 둔 접힘으로 돌려 연속 횟수에 셉니다. 패널 값 없는 응답자, 중복, 코드 이상, 추적 폴더 안의 행 단위 파일은 거부합니다.",
    },
    {
      what: "대용 자료 실행",
      state: str(`${ingest}.report_status`),
      ok: true,
      scope: `${str(`${ingest}.source_label`)}, 앵커 ${real.anchors_used.length}개, 응답자 ${num(`${ingest}.n_respondents`)}명, 패널 ${real.panel.model} ${real.panel.condition}. 이번 규칙 결과 ${str(`${ingest}.duel_outcome`)}, 평균 개선 ${signed(num(`${ingest}.pooled.mean_improvement`), 4)} ${ciText(interval(`${ingest}.pooled.interval`), 4)}. 시연 패널 조건인 C1이면 이 추출의 규칙 결과는 ${bool("stage4.posthoc.draw0_keep_at_frozen_fold_seed.terra_C1") ? "keep" : "drop"}입니다. 같은 규칙을 200회 추출에 돌리면 keep 비율은 Terra C2 ${pct(num(`${DUEL_T}.keep_rate`))}%, Terra C1 ${pct(num("stage4.posthoc.row.terra_C1.keep_rate"))}%입니다. 패널의 가치를 보여 주는 결과로 읽지 않습니다.`,
    },
    {
      what: "연속 keep 기록",
      state: `${health.consecutive_keeps}회, 횟수 ${required === null ? "합의 전" : `${required}회`}`,
      ok: false,
      scope: "대용 자료와 조사 단위 열이 없는 실행은 세지 않습니다. 횟수를 채워도 코드가 패널 값을 넣지 않고, 넣을 수 있다는 표시만 바뀝니다.",
    },
    {
      what: "콘셉트 문항 대결",
      state: "실제 설문을 만난 적 없음",
      ok: false,
      scope: `이번 실행은 앵커 문항만 넣었고(콘셉트 문항 ${real.concepts_used.length}개) 콘셉트 문항 대결을 돌리지 않았습니다. 콘셉트 열은 합성 답으로만 시험했습니다.`,
    },
    {
      what: "실제 응답자의 패널 값 만들기",
      state: "코드에 없음, 재료도 없음",
      ok: false,
      scope: "이 문항지로는 응답자 단위 패널 값을 만들 수 없습니다. 인구 항목은 연령대, 성별, 거주 지역, 가구원 수뿐이고, 패널의 C1 페르소나 변수 9개 중 동 구분, 직업, 학력, 혼인 상태, 소득이 없으며 C2 허용 문항도 없습니다. 실측과 패널 값을 같은 응답자로 묶으려면 이 변수를 문항지에 더해야 합니다.",
    },
    {
      what: "동결 기록",
      state: "사전 기준 통과, 라벨은 기록으로만",
      ok: false,
      scope: `동결 시드에서 대체 패널 keep rate ${num("stage4.duel.acceptance.surrogate_terra_slot.keep_rate")}, 양성 대조 ${fixed(num("stage4.duel.acceptance.positive_keep_rate"), 1)}로 사전 기준을 넘었습니다. 기준 ${stage4.duel_bar.surrogate_max_keep}는 「약 10%」를 고정 전에 작업자가 해석한 값이고, 대체 패널 값은 그 바로 아래입니다. 동결 뒤 다른 시드 ${SEED_RUNS.length}개로 돌리자 ${failed}개에서 기준을 넘었습니다. 시드가 적어 비율로 읽지 않고, 기준 근처에서 시드에 따라 갈린다는 뜻으로 읽습니다.`,
    },
    {
      what: "칸 오차 불일치",
      state: "대결의 오류율이 아님",
      ok: false,
      scope: `Terra C2에서 keep인 추출의 ${pct(num(`${DUEL_T}.false_keep_rate`))}%는 패널 밖 truth의 칸 오차로 R1을 이기지 못했고, R1을 이긴 추출의 ${pct(num(`${DUEL_T}.missed_keep_rate`))}%는 drop이었습니다. 대결은 개인 로그 손실을, 이 점검은 칸 오차를 봅니다.`,
    },
    {
      what: "실제 설문에 쓰기 전에 필요한 것",
      state: "새 사전 등록",
      ok: false,
      scope: "반복 접힘, 조사 단위를 온전히 둔 접힘, Terra C1, LLM 없는 floor, 상수 패널을 넣은 새 사전 등록을 계산 전에 커밋해야 합니다. 동결 계획은 고치지 않습니다.",
    },
    {
      what: "기록자와 사람의 결정",
      state: "사람이 하지 않음",
      ok: false,
      scope: `기록자 값은 「${stage4.ledger.approver}」이고 코드는 이 이름이 누구인지 확인하지 못합니다. 원장의 human_decision은 ${stage4.ledger.human_decision === null ? "비어 있습니다" : "채워져 있습니다"}. 사람이 터미널에서 입력하는 승인 명령 human-approve를 만들었지만 한 번도 실행하지 않았습니다.`,
    },
  ];
}

export function DuelStatusTable() {
  return (
    <div className="table-wrap">
      <table className="stack">
        <thead>
          <tr>
            <th style={{ width: "30%" }}>대상</th>
            <th style={{ width: "18%" }}>상태</th>
            <th>내용</th>
          </tr>
        </thead>
        <tbody>
          {duelRows().map((row) => (
            <tr key={row.what}>
              <td>{row.what}</td>
              <td data-label="상태">
                <span className={row.ok ? "status wrap-ok" : "status no wrap-ok"}>{row.state}</span>
              </td>
              <td>{row.scope}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Rate or a dash where the sheet holds no value, such as a false keep rate with no kept draw. */
export function rateOrDash(key: string, digits = 3): string {
  if (!has(key)) return "해당 없음";
  const value = any<number | null>(key);
  return value === null ? "해당 없음" : fixed(value, digits);
}
