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
                <span className="status">{str(`stage4.demo7.action.${row.card}`)}</span>
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
        {stage4.action.notes.map((line) => (
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

type StatusRow = { what: string; state: string; ok: boolean; scope: string };

function duelRows(): StatusRow[] {
  const real = stage4.real_results;
  const failed = seedRunsFailed();
  const keep = pct(num(`${DUEL_T}.keep_rate`));
  return [
    {
      what: "실측 파일을 받아 유지나 제외를 정하고 보고서와 원장에 적는 경로",
      state: "만듦, 대용 자료로 1회",
      ok: true,
      scope: "CSV 두 개(실측 응답, 같은 응답자의 패널 값)를 받아 200명 안의 5겹 교차 검증으로 R1과 겨룹니다. 패널 값 없는 응답자, 중복, 코드 이상, 추적 폴더 안의 행 단위 파일은 거부합니다.",
    },
    {
      what: "대용 자료 1회 실행",
      state: `${str("stage4.ingest.source_label")}, ${str("stage4.ingest.decision") === "keep" ? "유지" : "제외"}`,
      ok: true,
      scope: `앵커 ${real.anchors_used.length}개, 응답자 ${num("stage4.ingest.n_respondents")}명. 평균 개선 ${signed(num("stage4.ingest.pooled.mean_improvement"), 4)} ${ciText(interval("stage4.ingest.pooled.interval"), 4)}. 같은 규칙을 200회 추출에 돌리면 Terra C2는 ${keep}%에서 유지되므로 이번 유지는 그중 한 번입니다. 패널의 가치를 보여 주는 결과로 읽지 않습니다.`,
    },
    {
      what: "콘셉트 문항 대결",
      state: "실제 설문을 만난 적 없음",
      ok: false,
      scope: `이번 실행은 앵커 문항만 넣었고(콘셉트 문항 ${real.concepts_used.length}개) 콘셉트 문항 대결을 돌리지 않았습니다. 콘셉트 열은 합성 답으로만 시험했습니다.`,
    },
    {
      what: "실제 응답자의 패널 값 만들기",
      state: "코드에 없음",
      ok: false,
      scope: "그 응답자의 허용 문항으로 페르소나를 만들어 패널을 돌리는 단계입니다. 경로는 그 파일을 받는 데까지입니다.",
    },
    {
      what: "대결 규칙의 등급",
      state: "기준 근처",
      ok: false,
      scope: `동결 시드에서 사전 기준을 넘었습니다(대체 패널 유지율 ${num("stage4.duel.acceptance.surrogate_terra_slot.keep_rate")}, 기준 ${stage4.duel_bar.surrogate_max_keep} 이하). 답을 본 뒤 돌린 다른 시드 ${SEED_RUNS.length}개 중 ${failed}개에서 기준을 넘지 못했습니다. 확정 판정처럼 읽지 않습니다.`,
    },
    {
      what: "유지가 칸 오차까지 낫다는 뜻인가",
      state: "아님",
      ok: false,
      scope: `Terra C2에서 유지된 추출의 ${pct(num(`${DUEL_T}.false_keep_rate`))}%는 패널 밖 truth의 칸 오차로 R1을 이기지 못했고, 이긴 추출의 ${pct(num(`${DUEL_T}.missed_keep_rate`))}%는 제외됐습니다.`,
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

export function RealResultsPerItem() {
  const items = ["ever", "weekly", "carb"] as const;
  const perItem = stage4.real_results.anchors.per_item;
  return (
    <div className="table-wrap" tabIndex={0}>
      <table className="lead-col">
        <thead>
          <tr>
            <th>항목</th>
            <th>이 항목만 보면</th>
            <th className="num">평균 개선 [구간]</th>
            <th className="num">R1 로그 손실</th>
            <th className="num">보정 패널 로그 손실</th>
          </tr>
        </thead>
        <tbody>
          {items.map((id) => {
            const row = perItem[id];
            return (
              <tr key={id}>
                <td>{id}</td>
                <td>{row.keep ? "유지" : "제외"}</td>
                <td className="num">
                  {signed(row.mean_improvement, 5)} {ciText(row.interval as [number, number], 5)}
                </td>
                <td className="num">{fixed(row.r1_loss, 5)}</td>
                <td className="num">{fixed(row.panel_loss, 5)}</td>
              </tr>
            );
          })}
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
