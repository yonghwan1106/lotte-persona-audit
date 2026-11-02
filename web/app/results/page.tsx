import type { Metadata } from "next";
import { DotRows, Legend, MaeExplorer, type DotRow, type MaeCell, type Pair } from "@/components/charts";
import { COLOR } from "@/lib/colors";
import { Caveats, SourceLine } from "@/components/Notes";
import { HealthCheckDecision, rateOrDash, seedRunsFailed, SEED_RUNS } from "@/components/Stage4";
import { AgePanel, GenderDumbbell, Key, SlopeChart, Strip, type GenderRow } from "@/components/viz/Charts";
import { Evidence, Figure, Glossary, Scene } from "@/components/viz/Scene";
import controls from "@/data/controls.json";
import stage4 from "@/data/stage4.json";
import viz from "@/data/viz.json";
import { any, bool, caveats, caveatsOf, ciText, fixed, has, interval, num, signed, sources } from "@/lib/numbers";

export const metadata: Metadata = { title: "측정 결과 · 합성 패널 감사 기록" };

const ITEM_NAME: Record<string, string> = { ever: "제로 음료 경험", weekly: "제로 음료 주 1회 이상", carb: "탄산 1순위" };
const ITEMS = [
  { id: "ever", label: "ever: 제로 음료를 마셔 본 적 있음" },
  { id: "weekly", label: "weekly: 제로 음료 주 1회 이상" },
  { id: "carb", label: "carb: 가장 좋아하는 음료 1순위가 탄산" },
];
const COMBOS = [
  { id: "terra_C2", label: "Terra C2" },
  { id: "terra_C1", label: "Terra C1" },
  { id: "luna_C2", label: "Luna C2" },
  { id: "luna_C1", label: "Luna C1" },
];

function pair(prefix: string): Pair | null {
  if (!has(`${prefix}.mean_diff`)) return null;
  return { d: num(`${prefix}.mean_diff`), ci: interval(`${prefix}.ci95`) };
}

function maeCell(combo: string, item: string): MaeCell {
  const est = (kind: string, e: string) => (e === "E2" || e === "R1" || e === "E0" || e === "E1" ? `stage2.n200.${kind}.${e}.${item}` : `stage2.n200.${kind}.${combo}.${e}.${item}`);
  const level = (kind: string) => Object.fromEntries(["E3", "E2", "E4", "E5", "E6", "R1"].map((e) => [e, num(`${est(kind, e)}.cell_mae`)]));
  const collect = (kind: string, against: string, list: string[]) => {
    const out: Record<string, Pair> = {};
    for (const e of list) {
      const found = pair(`${est(kind, e)}.minus_${against}`);
      if (found) out[e] = found;
    }
    return out;
  };
  return {
    level: { row: level("row"), cluster: level("cluster") },
    minusE2: { row: collect("row", "E2", ["E3", "R1", "E4", "E5", "E6"]), cluster: collect("cluster", "E2", ["E3", "R1", "E4", "E5", "E6"]) },
    minusR1: { row: collect("row", "R1", ["E4", "E5", "E6"]), cluster: collect("cluster", "R1", ["E4", "E5", "E6"]) },
    floor: num(`stage2.noise_floor.${item}`),
  };
}

function levelRows(): DotRow[] {
  return ITEMS.map((item) => {
    const base = `stage2.stereotype.${item.id}`;
    const real = num(`${base}.real_national_pct`);
    const main = num(`${base}.terra_C2.bias_pp`);
    const others = COMBOS.slice(1).map((c) => ({ c, bias: num(`${base}.${c.id}.bias_pp`) }));
    return {
      label: item.id,
      value: `실제 ${fixed(real)}% · Terra C2 ${signed(main)}pp`,
      link: [real, real + main] as [number, number],
      marks: [
        ...others.map(({ bias }) => ({ x: real + bias, fill: COLOR.panel, hollow: true, small: true })),
        { x: real, fill: COLOR.real },
        { x: real + main, fill: COLOR.panel },
      ],
      tip: `${item.label}. 실제 ${fixed(real)}%. 편향 ${COMBOS.map((c) => `${c.label} ${signed(num(`${base}.${c.id}.bias_pp`))}pp`).join(", ")}`,
    };
  });
}


const RANK_SET = "ranking.merged_coffee_15";
const RANK_ROWS = [
  { key: "panel_C2", label: "패널 Terra C2", fill: COLOR.panel, hollow: false },
  { key: "panel_C1", label: "패널 Terra C1", fill: COLOR.panel, hollow: true },
  { key: "direct_row", label: "실제 200명 row", fill: COLOR.real, hollow: false },
  { key: "direct_cluster", label: "실제 200명 cluster", fill: COLOR.real, hollow: true },
  { key: "krei_2024", label: "2024 원자료 집계", fill: COLOR.reference, hollow: false },
];

function rankRows(metric: string, digits: number): DotRow[] {
  return RANK_ROWS.map((r) => {
    const value = num(`${RANK_SET}.${r.key}.${metric}.value`);
    const ci = interval(`${RANK_SET}.${r.key}.${metric}.ci95`);
    return {
      label: r.label,
      value: `${fixed(value, digits)} ${ciText(ci, digits, false)}`,
      marks: [{ x: value, lo: ci[0], hi: ci[1], fill: r.fill, hollow: r.hollow }],
      tip: `${r.label}: ${fixed(value, 4)}, 95% 구간 ${ciText(ci, 4, false)}`,
    };
  });
}

const BANDS = [
  { id: "under_1pp", label: "1pp 미만" },
  { id: "1_to_3pp", label: "1~3pp" },
  { id: "3_to_5pp", label: "3~5pp" },
  { id: "5pp_and_over", label: "5pp 이상" },
];

const ALLOC = "stage4.allocation.R1.panel_excluded.cell_mae";
const DESIGNS = [
  { id: "equal", label: "균등" },
  { id: "proportional", label: "비례" },
  { id: "panel_neyman", label: "패널 Neyman (3항목 평균 기준)" },
  { id: "reference_neyman", label: "reference Neyman (3항목 평균 기준)" },
  { id: "panel_neyman_by_item", label: "패널 Neyman (항목별)" },
  { id: "reference_neyman_by_item", label: "reference Neyman (항목별)" },
];
const ALLOC_ITEMS = ["ever", "weekly", "carb", "average"];
const ALLOC_COMBOS = [
  { est: "R1", truth: "panel_excluded", metric: "cell_mae", label: "R1, 패널 밖 truth, 칸 MAE (주 지표)" },
  { est: "R1", truth: "panel_excluded", metric: "national_error", label: "R1, 패널 밖 truth, 전국 오차" },
  { est: "R1", truth: "whole_test", metric: "cell_mae", label: "R1, 시험 전체 truth, 칸 MAE" },
  { est: "R1", truth: "pool_own", metric: "cell_mae", label: "R1, 풀 자체 truth, 칸 MAE" },
  { est: "shrink", truth: "panel_excluded", metric: "cell_mae", label: "수축, 패널 밖 truth, 칸 MAE" },
  { est: "shrink", truth: "panel_excluded", metric: "national_error", label: "수축, 패널 밖 truth, 전국 오차" },
  { est: "direct", truth: "panel_excluded", metric: "cell_mae", label: "직접, 패널 밖 truth, 칸 MAE" },
  { est: "direct", truth: "panel_excluded", metric: "national_error", label: "직접, 패널 밖 truth, 전국 오차" },
];
const SIGNALS = [
  { id: "terra_minus_luna", label: "모델 간 차이 (Terra - Luna)" },
  { id: "c1_minus_c2", label: "조건 간 차이 (C1 - C2)" },
  { id: "repeat_sd", label: "반복 응답 편차" },
  { id: "panel_level", label: "패널 수준 (비교용, 사전 기준 없음)" },
];
const DUEL_PANELS = [
  { id: "terra_C2", label: "Terra C2", fill: COLOR.panel, hollow: false },
  { id: "luna_C1", label: "Luna C1", fill: COLOR.panel, hollow: true },
  { id: "control_s0.25", label: "양성 대조 s=0.25", fill: COLOR.real, hollow: true },
  { id: "control_s0.5", label: "양성 대조 s=0.5", fill: COLOR.real, hollow: true },
  { id: "control_s1.0", label: "양성 대조 s=1.0 (기준)", fill: COLOR.real, hollow: false },
  { id: "control_s2.0", label: "양성 대조 s=2.0", fill: COLOR.real, hollow: true },
  { id: "surrogate_terra_slot", label: "대체 패널, Terra 자리", fill: COLOR.reference, hollow: false },
  { id: "surrogate_luna_slot", label: "대체 패널, Luna 자리", fill: COLOR.reference, hollow: true },
];


export default function ResultsPage() {
  const data: Record<string, Record<string, MaeCell>> = {};
  for (const combo of COMBOS) {
    data[combo.id] = {};
    for (const item of [...ITEMS, { id: "average", label: "" }]) data[combo.id][item.id] = maeCell(combo.id, item.id);
  }

  const verdictCombos = COMBOS.flatMap((c) => ITEMS.map((i) => ({ c, i })));
  const stageKeys = ITEMS.map((i) => `stage2.stereotype.${i.id}.terra_C2.bias_pp`);
  const genderKeys = ITEMS.flatMap((i) => [`stage2.stereotype.${i.id}.real_gender_gap_pp`, `stage2.stereotype.${i.id}.terra_C2.gender_gap_pp`]);
  const v3 = "verdict.llm";
  const cellDiff = Math.max(...any<number[]>("stage4.allocation.n_per_cell.panel_neyman").map((n, i) => Math.abs(n - any<number[]>("stage4.allocation.n_per_cell.proportional")[i])));
  const namingSignals = SIGNALS.filter((s) => has(`stage4.flags.${s.id}.names_wrong_cells`));
  const namedCount = namingSignals.filter((s) => bool(`stage4.flags.${s.id}.names_wrong_cells`)).length;
  const duelT = "stage4.duel.row.terra_C2.pooled.panel_excluded";
  const failures: { rule: string; result: string; read: React.ReactNode }[] = [
    {
      rule: "패널 + 200명이 같은 200명의 회귀(R1)를 이기는가",
      result: "row와 cluster 모두에서 이긴 조합 0개",
      read: `Terra C2 E4 - R1 ${signed(num("stage2.n200.row.terra_C2.E4.average.minus_R1.mean_diff"))}pp ${ciText(interval("stage2.n200.row.terra_C2.E4.average.minus_R1.ci95"))}(row). 응답자 본인의 실제 답을 넣은 패널도 규칙 v2에서 통과하지 못해, LLM 실패의 증거로 읽지 않습니다.`,
    },
    {
      rule: "규칙 v1 (사전 고정, 상대는 E2)",
      result: `LLM ${num(`${v3}.v1.count.보정 후 참고`)}개 모두 보정 후 참고`,
      read: `이 라벨은 E2를 이겼다는 뜻일 뿐이고 Terra와 Luna, C1과 C2를 구별하지 못합니다. 평균 차이 ${fixed(Math.abs(num("stage2.n200.row.terra_C2.E4.average.minus_E2.mean_diff")))}pp는 사전 등록한 noise floor ${fixed(num("stage2.noise_floor.average"))}pp보다 작습니다.`,
    },
    {
      rule: "규칙 v2 (답을 본 뒤에 씀)",
      result: `보정 후 참고 0개, 방향만 ${num(`${v3}.v2.count.방향만`)}, 실측 전용 ${num(`${v3}.v2.count.실측 전용`)}`,
      read: "사전 등록이 아닙니다. 실제 답 대조군도 보정 후 참고를 받지 못합니다.",
    },
    {
      rule: "규칙 v3 (답을 본 뒤에 씀)",
      result: `LLM 보정 후 참고 0개, 방향만 ${num(`${v3}.v3.count.방향만`)}, 판정 불가 ${num(`${v3}.v3.count.판정 불가`)}`,
      read: "규칙이 LLM을 가려낸다고 읽지 않습니다. 첫 분기는 실제 답에 가까운 패널에서만 작동합니다. 제품 라벨로 쓰지 않습니다.",
    },
    {
      rule: "패널 밖 truth로 다시 본 E2 대비 우위",
      result: "안정적으로 남는 것은 ever뿐",
      read: `채점 truth의 psfwt ${fixed(num("stage2.panel_share_of_test_psfwt"))}%가 패널 본인입니다. weekly와 carb의 우위는 유지되지 않았습니다.`,
    },
    {
      rule: "A15 순서 시험의 고정 판정",
      result: "넘지 못함",
      read: "truth와 똑같은 추정치도 3~5pp와 5pp 이상 구간에서 넘지 못하는 규칙이라 변별 근거로 쓰지 않습니다. 근거는 쌍 차이입니다.",
    },
    {
      rule: "패널이 실측 200명 배분을 돕는가 (사전 기준 2개)",
      result: `비례 대비 ${bool("stage4.allocation.reading.panel_helps_over_proportional") ? "통과" : "미달"}, reference 대비 ${bool("stage4.allocation.reading.panel_adds_over_reference") ? "통과" : "미달"}`,
      read: `패널 배분 - 비례 평균 ${signed(num(`${ALLOC}.panel_neyman_minus_proportional.average.mean_diff`), 3)}pp, 추출별 차이의 95% 범위 ${ciText(interval(`${ALLOC}.panel_neyman_minus_proportional.average.ci95`), 3)}. 이 기준은 정답을 아는 oracle 배분도 넘지 못하므로 미달을 패널 실패의 증거로 읽지 않습니다. 근거는 평균 차이의 크기입니다. 7절`,
    },
    {
      rule: "실측 전에 틀린 칸을 지목하는가 (신호 3개)",
      result: `사전 기준을 넘은 신호 ${namedCount}개`,
      read: "지목한다는 증거가 없다는 뜻이고, 이 시험은 검정력이 낮아 신호가 쓸모없다는 증명은 아닙니다. 8절",
    },
    {
      rule: "정답 없는 대결 규칙 (사전 기준)",
      result: `동결 시드 통과, 건강검진으로 내림`,
      read: `대체 패널 keep rate ${num("stage4.duel.acceptance.surrogate_terra_slot.keep_rate")}, 기준 ${stage4.duel_bar.surrogate_max_keep} 이하. 다른 시드 ${SEED_RUNS.length}개 중 ${seedRunsFailed()}개는 기준을 넘었고, 같은 표본에서 접힘 시드만 바꿔도 결정이 뒤집힙니다. 통과를 본 뒤의 사후 결정으로 패널 값은 기본 제외입니다. 9절`,
    },
    {
      rule: "콘셉트 문항 대결",
      result: "돌리지 않음",
      read: "콘셉트 문항 대결은 실제 설문을 만난 적이 없습니다.",
    },
  ];

  const ageItems = ["ever", "weekly", "carb"] as const;
  const ageExceptions = ageItems.flatMap((item) =>
    Object.entries(viz.age_bands[item]).flatMap(([combo, block]) => block.rows.filter((row) => row.panel <= row.real).map((row) => `${combo} ${ITEM_NAME[item]} ${row.band}`)),
  );
  const forestRows: DotRow[] = [
    { heading: "패널을 실제 200명에 맞추는 세 방법" },
    ...[
      { e: "E4", name: "높이만 맞춤" },
      { e: "E5", name: "높이와 기울기 맞춤" },
      { e: "E6", name: "칸별로 맞춤" },
    ].flatMap(({ e, name }) =>
      [
        { kind: "row", kindName: "응답자 단위 추출" },
        { kind: "cluster", kindName: "조사 단위 추출" },
      ].map(({ kind, kindName }) => {
        const base = `stage2.n200.${kind}.terra_C2.${e}.average.minus_R1`;
        const d = num(`${base}.mean_diff`);
        const ci = interval(`${base}.ci95`);
        return {
          label: `${name}, ${kindName}`,
          value: `${signed(d)} ${ciText(ci)}`,
          marks: [{ x: d, lo: ci[0], hi: ci[1], fill: COLOR.calibrated, hollow: kind === "cluster" }],
          tip: `${name}, ${kindName}: 단순 통계와의 오차 차이 ${signed(d, 3)}%⁠포인트, 범위 ${ciText(ci, 3)}`,
        };
      }),
    ),
  ];
  const rankRows2 = viz.ranking;
  const moved = [...rankRows2].filter((r) => Math.abs(r.panel_rank - r.real_rank) >= 4).sort((a, b) => Math.abs(b.panel_rank - b.real_rank) - Math.abs(a.panel_rank - a.real_rank));
  const zero = rankRows2.find((r) => r.id === "8")!;
  const milk = rankRows2.find((r) => r.id === "3")!;
  const pairRows: DotRow[] = [
    { key: "panel_C2", label: "패널", fill: COLOR.panel },
    { key: "direct_row", label: "실제 200명", fill: COLOR.real },
    { key: "krei_2024", label: "지난해 집계", fill: COLOR.reference },
  ].map((r) => {
    const value = num(`${RANK_SET}.${r.key}.pair_accuracy.value`);
    const ci = interval(`${RANK_SET}.${r.key}.pair_accuracy.ci95`);
    return { label: r.label, value: fixed(value, 3), marks: [{ x: value, lo: ci[0], hi: ci[1], fill: r.fill }], tip: `${r.label} ${fixed(value, 3)}, 범위 ${ciText(ci, 3, false)}` };
  });
  const genderData: GenderRow[] = ITEMS.map((item) => {
    const base = `stage2.stereotype.${item.id}`;
    const real = num(`${base}.real_gender_gap_pp`);
    const realCi = interval(`${base}.real_gender_gap_ci95`);
    const panel = num(`${base}.terra_C2.gender_gap_pp`);
    return {
      id: item.id,
      label: ITEM_NAME[item.id],
      real,
      realCi,
      panel,
      panelCi: viz.gender[item.id as "ever"].panel_ci95 as [number, number],
      opposite: Math.sign(real) !== Math.sign(panel),
      zeroInReal: realCi[0] <= 0 && realCi[1] >= 0,
    };
  });
  const everGap = genderData[0];
  const aucRows: DotRow[] = ITEMS.map((item) => {
    const auc = num(`stage2.person.${item.id}.terra_C2.auc`);
    const floor = num(`stage2.person.${item.id}.floor_auc`);
    return {
      label: ITEM_NAME[item.id],
      value: `패널 ${fixed(auc, 3)}, 바닥 ${fixed(floor, 3)}`,
      link: [floor, auc] as [number, number],
      marks: [
        { x: floor, fill: COLOR.reference },
        { x: auc, fill: COLOR.panel },
      ],
      tip: `${ITEM_NAME[item.id]}: 패널 ${fixed(auc, 4)}, 나이·성별 바닥 ${fixed(floor, 4)}`,
    };
  });
  const keepPanel = (label: string, base: string, fill: string, hollow = false) => {
    const rate = num(`${base}.keep_rate`);
    const ci = interval(`${base}.keep_rate_ci95`);
    return { label, value: `${fixed(rate, 3)} ${ciText(ci, 3, false)}`, marks: [{ x: rate, lo: ci[0], hi: ci[1], fill, hollow }], tip: `${label}: ${fixed(rate, 3)}, 범위 ${ciText(ci, 3, false)}` };
  };
  const keepRows: DotRow[] = [
    { heading: "GPT 패널" },
    keepPanel("Terra, 음료 외 문항 더함", "stage4.duel.row.terra_C2.pooled.panel_excluded", COLOR.panel),
    keepPanel("Terra, 인구 특성만 (시연 조건)", "stage4.posthoc.row.terra_C1", COLOR.panel),
    keepPanel("Luna, 인구 특성만", "stage4.duel.row.luna_C1.pooled.panel_excluded", COLOR.panel, true),
    { heading: "LLM이 아닌 비교 대상" },
    keepPanel("답을 일부 알려 준 양성 대조", "stage4.duel.row.control_s1.0.pooled.panel_excluded", COLOR.real),
    keepPanel("대체 패널, Terra 자리", "stage4.duel.row.surrogate_terra_slot.pooled.panel_excluded", COLOR.reference),
    keepPanel("대체 패널, Luna 자리", "stage4.duel.row.surrogate_luna_slot.pooled.panel_excluded", COLOR.reference, true),
    keepPanel("LLM 없는 나이·성별 모델", "stage4.posthoc.row.floor_no_llm", COLOR.reference),
  ];
  const RULE_COLOR: Record<string, { color: string; hollow?: boolean }> = {
    "보정 후 참고": { color: COLOR.real },
    방향만: { color: "#8CC7D3" },
    "실측 전용": { color: "#567079" },
    "판정 불가": { color: "#12323B", hollow: true },
  };
  const ruleCell = (prefix: string, rule: string) => {
    const labels = Object.keys(RULE_COLOR).filter((name) => has(`${prefix}.${rule}.count.${name}`) && num(`${prefix}.${rule}.count.${name}`) > 0);
    const text = labels.map((name) => `${name} ${num(`${prefix}.${rule}.count.${name}`)}`).join(", ");
    return (
      <td>
        <Strip className="rule-strip" label={text} cells={labels.flatMap((name) => Array.from({ length: num(`${prefix}.${rule}.count.${name}`) }, () => ({ ...RULE_COLOR[name], tip: name })))} />
        {text}
      </td>
    );
  };
  const allocRows: DotRow[] = DESIGNS.slice(0, 4).map((design) => {
    const value = num(`${ALLOC}.${design.id}.average.mean`);
    return { label: design.label.replace(" (3항목 평균 기준)", "").replace("Neyman", "배분").replace("reference", "참고 자료"), value: fixed(value, 2), marks: [{ x: value, fill: design.id.startsWith("panel") ? COLOR.panel : COLOR.real }], tip: `${design.label}: ${fixed(value, 3)}%⁠포인트` };
  });
  const flagRows: DotRow[] = namingSignals.map((s) => {
    const observed = num(`stage4.flags.${s.id}.overlap_top9.observed`);
    const band = stage4.flags_random_95[s.id as "terra_minus_luna"] as [number, number];
    return {
      label: s.label.replace(" (Terra - Luna)", "").replace(" (C1 - C2)", ""),
      value: `${observed}칸`,
      marks: [{ x: num(`stage4.flags.${s.id}.overlap_top9.random_mean`), lo: band[0], hi: band[1], fill: COLOR.reference, hollow: true }, { x: observed, fill: COLOR.panel }],
      tip: `${s.label}: 겹친 칸 ${observed}개, 무작위 95 범위 ${ciText(band, 0, false)}`,
    };
  });

  return (
    <>
      <Scene className="page-head" id="failures">
        <h1>측정 결과</h1>
        <p className="lead">기존 음료 행동을 KREI 2025 시험 분할로 쟀습니다. 3개 항목과 12칸(연령대와 성별)이고, 신제품 성패와 새 콘셉트 반응은 재지 않았습니다.</p>
        <Evidence summary="넘지 못한 규칙과 읽는 법, 표기 보기">
          <p>수치는 수치 시트(results/numbers_sheet.json)에서 읽고, 대결 규칙의 기준값과 칸 이름만 그 출처 파일에서 읽습니다. 규칙과 기준을 넘지 못한 것, 넘었지만 그렇게 읽으면 안 되는 것을 먼저 적습니다. 자세한 값은 아래 절에 있습니다.</p>
      <div className="table-wrap">
        <table className="stack">
          <thead>
            <tr>
              <th style={{ width: "30%" }}>규칙이나 기준</th>
              <th style={{ width: "24%" }}>결과</th>
              <th>읽는 법</th>
            </tr>
          </thead>
          <tbody>
            {failures.map((f) => (
              <tr key={f.rule}>
                <td>{f.rule}</td>
                <td data-label="결과">
                  <strong>{f.result}</strong>
                </td>
                <td>{f.read}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small">
        에이전트 방어에서 뚫린 것과 아직 통과하는 것은 <a href="/attacks">공격 기록</a>에 있습니다.
      </p>

      <h4>읽는 데 필요한 표기</h4>
      <div className="table-wrap">
        <table className="stack">
          <tbody>
            <tr>
              <td>
                <code>ever</code> <code>weekly</code> <code>carb</code>
              </td>
              <td>제로 음료를 마셔 본 적 있음, 제로 음료 주 1회 이상, 가장 좋아하는 음료 1순위가 탄산(가당과 무가당 포함).</td>
            </tr>
            <tr>
              <td>Terra, Luna, C1, C2</td>
              <td>모델 gpt-6.1-terra, gpt-6-luna. C1은 인구 특성만 쓴 페르소나, C2는 인구 특성에 음료가 아닌 허용 목록 문항을 더한 페르소나입니다.</td>
            </tr>
            <tr>
              <td>E2, E3, E4~E6, R1</td>
              <td>E2: 실제 200명의 칸 평균을 전체 평균 쪽으로 수축. E3: 패널 원수치. E4~E6: 패널을 실제 200명으로 보정(절편, 절편과 기울기, 칸 잔차). R1: 패널 없이 같은 200명으로 적합한 나이·성별 회귀.</td>
            </tr>
            <tr>
              <td>row, cluster</td>
              <td>실제 200명을 뽑는 방식입니다. row는 행 단위, cluster는 조사 단위 통째입니다. 둘을 함께 보고 한쪽만 인용하지 않습니다.</td>
            </tr>
          </tbody>
        </table>
      </div>
        </Evidence>
      </Scene>

      <Scene tone="glass" id="age">
        <h2>패널은 모든 연령대에서 실제보다 높게 답합니다</h2>
        <p className="say">나이에 따른 방향은 비슷하지만 크기가 다릅니다. 색칠한 폭이 실제 응답과의 차이이고, 패널 값은 시장 수치가 아닙니다.</p>
        <Key
          items={[
            { label: "실제 응답", color: COLOR.real },
            { label: "GPT 패널 300명", color: COLOR.panel },
            { label: "차이", color: COLOR.yuzu, shape: "area" },
          ]}
        />
        <Figure label={`연령대별 비율 선 그림, 0에서 100까지 같은 눈금입니다. ${ageItems.map((item) => `${ITEM_NAME[item]}: ${viz.age_bands[item].terra_C2.rows.map((r) => `${r.band} 실제 ${r.real.toFixed(1)}, 패널 ${r.panel.toFixed(1)}`).join(", ")}`).join(". ")}. 패널 값은 시장 수치가 아닙니다.`}>
          <div className="age-grid">
            {ageItems.map((item) => (
              <AgePanel key={item} title={ITEM_NAME[item]} rows={viz.age_bands[item].terra_C2.rows} />
            ))}
          </div>
        </Figure>
        <Evidence summary="연령대 표와 수준 편향 보기">
          <Glossary />
          <p>위 그림의 패널은 관문 실행의 Terra C2 300명이고, 실제 응답은 시험 truth 전체입니다. 그림은 results/gate/gate_explore_gpt-6.1-terra.json의 탐색 집계이고 사전 등록한 지표가 아닙니다. 같은 파일의 칸 상관은 {ageItems.map((item) => `${ITEM_NAME[item]} ${viz.age_bands[item].terra_C2.cell_pearson_r}`).join(", ")}입니다.</p>
          <p>패널이 실제보다 낮거나 같은 연령대: {ageExceptions.length ? ageExceptions.join(", ") : "없음"}. 그래서 제목의 「모든 연령대」는 Terra C2와 Terra C1에 대한 말입니다.</p>
          <div className="table-wrap" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>항목</th>
                  <th>연령대</th>
                  <th className="num">실제 %</th>
                  <th className="num">Terra C2</th>
                  <th className="num">Terra C1</th>
                  <th className="num">Luna C2</th>
                  <th className="num">Luna C1</th>
                </tr>
              </thead>
              <tbody>
                {ageItems.flatMap((item) =>
                  viz.age_bands[item].terra_C2.rows.map((row, i) => (
                    <tr key={item + row.band}>
                      <td>{ITEM_NAME[item]}</td>
                      <td>{row.band}</td>
                      <td className="num">{row.real.toFixed(2)}</td>
                      <td className="num">{row.panel.toFixed(2)}</td>
                      <td className="num">{viz.age_bands[item].terra_C1.rows[i].panel.toFixed(2)}</td>
                      <td className="num">{viz.age_bands[item].luna_C2.rows[i].panel.toFixed(2)}</td>
                      <td className="num">{viz.age_bands[item].luna_C1.rows[i].panel.toFixed(2)}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
      <h3>1. 수준 편향: 패널 원수치와 실제 값</h3>
      <div className="figure">
        <div className="figure-title">전국 비율, 실제 값과 패널 원수치의 차이</div>
        <div className="figure-sub">패널 위치는 시트의 실제 값에 bias_pp를 더해 찍었습니다. 패널 원수치는 시장 수치로 쓰지 않습니다.</div>
        <Legend
          items={[
            { label: "실제 (시험 truth 전체)", fill: COLOR.real },
            { label: "Terra C2", fill: COLOR.panel },
            { label: "다른 3개 조합", fill: COLOR.panel, hollow: true },
          ]}
        />
        <DotRows ariaLabel="항목별 실제 값과 패널 원수치" rows={levelRows()} domain={[0, 80]} ticks={[0, 20, 40, 60, 80]} tickStyle="percent" axisLabel="응답자 비율" />
        <details>
          <summary>표로 보기</summary>
          <div className="table-wrap" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>항목</th>
                  <th className="num">실제 %</th>
                  {COMBOS.map((c) => (
                    <th className="num" key={c.id}>
                      {c.label} 편향 pp
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ITEMS.map((i) => (
                  <tr key={i.id}>
                    <td>{i.label}</td>
                    <td className="num">{fixed(num(`stage2.stereotype.${i.id}.real_national_pct`))}</td>
                    {COMBOS.map((c) => (
                      <td className="num" key={c.id}>
                        {signed(num(`stage2.stereotype.${i.id}.${c.id}.bias_pp`))}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>
      <Caveats items={caveats(stageKeys)} />
      <SourceLine files={sources(stageKeys)} keys="stage2.stereotype.*" />
        </Evidence>
      </Scene>

      <Scene id="forest">
        <h2>보정한 패널은 단순 통계와 구별되지 않습니다</h2>
        <p className="say">점이 0보다 왼쪽이면 패널 쪽 오차가 작습니다. 칸별로 맞춘 경우만 응답자 단위 추출에서 오차가 더 컸고, 조사 단위 추출에서는 구별되지 않았습니다.</p>
        <div className="chart-narrow">
          <DotRows
            ariaLabel={`보정한 패널과 패널 없는 단순 통계의 오차 차이. ${forestRows.filter((r) => r.label).map((r) => `${r.label} ${r.value}`).join(", ")}. 세 항목 평균, 단위는 %⁠포인트입니다.`}
            rows={forestRows}
            domain={[-2.5, 2.5]}
            ticks={[-2, -1, 0, 1, 2]}
            tickStyle="signed"
            axisLabel="단순 통계와의 오차 차이, %⁠포인트"
            refs={[{ x: 0, label: "차이 없음" }]}
          />
        </div>
        <Evidence summary="항목별 오차 탐색기와 비교 상대 보기">
          <Glossary />
      <h3>2. 칸 오차 사다리: 패널 원수치, E2, 보정, R1</h3>
      <p>
        질문은 하나입니다. 합성 패널에 실제 약 200명을 더한 것이 그 200명만 쓴 것을 이기는가. 사전 고정한 규칙의 비교 상대인 E2보다는 3개 항목 평균 cell MAE가 {fixed(Math.abs(num("stage2.n200.row.terra_C2.E4.average.minus_E2.mean_diff")))}pp(E4), {fixed(Math.abs(num("stage2.n200.row.terra_C2.E5.average.minus_E2.mean_diff")))}pp(E5), {fixed(Math.abs(num("stage2.n200.row.terra_C2.E6.average.minus_E2.mean_diff")))}pp(E6) 낮았습니다(Terra C2, row). 같은 200명의 R1과 비교하면 E4 차이는 {signed(num("stage2.n200.row.terra_C2.E4.average.minus_R1.mean_diff"))}pp {ciText(interval("stage2.n200.row.terra_C2.E4.average.minus_R1.ci95"))}(row), {signed(num("stage2.n200.cluster.terra_C2.E4.average.minus_R1.mean_diff"))}pp {ciText(interval("stage2.n200.cluster.terra_C2.E4.average.minus_R1.ci95"))}(cluster)로 구별되지 않았습니다. E6은 row 추출에서 {signed(num("stage2.n200.row.terra_C2.E6.average.minus_R1.mean_diff"))}pp {ciText(interval("stage2.n200.row.terra_C2.E6.average.minus_R1.ci95"))}로 더 나빴고, cluster에서는 {signed(num("stage2.n200.cluster.terra_C2.E6.average.minus_R1.mean_diff"))}pp {ciText(interval("stage2.n200.cluster.terra_C2.E6.average.minus_R1.ci95"))}로 구별되지 않았습니다.
      </p>
      <p>
        평균 차이는 사전 등록한 noise floor {fixed(num("stage2.noise_floor.average"))}pp보다 작습니다. 채점 truth의 psfwt 질량 {fixed(num("stage2.panel_share_of_test_psfwt"))}%가 패널 본인이고, 패널 밖 truth로 다시 보면 E2 대비 규칙을 안정적으로 통과하는 것은 ever뿐이며 weekly와 carb의 우위는 유지되지 않았습니다.
      </p>
      <MaeExplorer models={COMBOS} items={[...ITEMS, { id: "average", label: "3항목 평균" }]} data={data} />
      <Caveats items={caveatsOf(["stage2.n200.row.terra_C2.E4.average", "stage2.noise_floor.average", "stage2.panel_share_of_test_psfwt", "stage2.n200.row.terra_C2.E3.average.cell_mae"])} />
      <SourceLine files={sources(["stage2.n200.row.terra_C2.E4.average.cell_mae"])} keys="stage2.n200.*, stage2.noise_floor.*" />
          <div className="table-wrap" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>위 그림</th>
                  <th className="num">차이 pp [범위]</th>
                </tr>
              </thead>
              <tbody>
                {forestRows.filter((r) => r.label).map((r) => (
                  <tr key={r.label}>
                    <td>{r.label}</td>
                    <td className="num">{r.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Evidence>
      </Scene>

      <Scene tone="glass" id="ranking">
        <h2>음료 순서는 실제 200명과 지난해 집계보다 덜 맞습니다</h2>
        <p className="say">
          패널은 {zero.label}을 {zero.real_rank}위에서 {zero.panel_rank}위로 올리고, {milk.label}를 {milk.real_rank}위에서 {milk.panel_rank}위로 내립니다. 기존 음료의 1순위 점유이고, 신제품 순서가 아닙니다.
        </p>
        <Key
          items={[
            { label: "패널이 4계단 이상 올린 음료", color: COLOR.panel },
            { label: "패널이 4계단 이상 내린 음료", color: COLOR.real },
          ]}
        />
        <div className="slope-wrap">
          <SlopeChart
            rows={rankRows2}
            label={`음료 15범주의 실제 순위와 패널 순위 기울기 그림. 많이 움직인 범주: ${moved.map((r) => `${r.label} ${r.real_rank}위에서 ${r.panel_rank}위`).join(", ")}. 패널 값은 시장 수치가 아닙니다.`}
          />
          <div className="slope-side">
            <h3>많이 움직인 음료</h3>
            <ul>
              {moved.map((r) => (
                <li key={r.id}>
                  <strong>{r.label}</strong> {r.real_rank}위에서 {r.panel_rank}위
                </li>
              ))}
            </ul>
            <h3>두 음료 중 더 많은 쪽을 맞힌 비율</h3>
            <DotRows
              ariaLabel={`쌍 정확도. ${pairRows.map((r) => `${r.label} ${r.value}`).join(", ")}.`}
              rows={pairRows}
              domain={[0.5, 1]}
              ticks={[0.5, 0.75, 1]}
              axisLabel="쌍 정확도"
            />
          </div>
        </div>
        <Evidence summary="15범주 표와 순위 상관, 구간별 쌍 정확도 보기">
          <Glossary />
          <p className="small">범주 이름은 줄여 적었고 KREI 문항 원문은 싣지 않습니다. 커피는 두 보기를 합친 값입니다. 실제 값은 패널 밖 truth, 패널은 Terra C2입니다.</p>
          <div className="table-wrap" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>범주</th>
                  <th className="num">실제 순위</th>
                  <th className="num">실제 %</th>
                  <th className="num">패널 순위</th>
                  <th className="num">패널 %</th>
                </tr>
              </thead>
              <tbody>
                {rankRows2.map((r) => (
                  <tr key={r.id}>
                    <td>{r.label}</td>
                    <td className="num">{r.real_rank}</td>
                    <td className="num">{r.real_share.toFixed(2)}</td>
                    <td className="num">{r.panel_rank}</td>
                    <td className="num">{r.panel_share.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
      <h3>3. 순서: 패널, 실제 200명, 2024 원자료</h3>
      <p>
        패널 밖 truth로 본 A15 순서 시험(기존 음료, 15범주)입니다. Terra C2의 Spearman은 {fixed(num(`${RANK_SET}.panel_C2.spearman.value`), 3)}, 쌍 정확도는 {fixed(num(`${RANK_SET}.panel_C2.pair_accuracy.value`), 3)}였습니다. 실제 200명 직접 추정(row)은 {fixed(num(`${RANK_SET}.direct_row.spearman.value`), 3)}, {fixed(num(`${RANK_SET}.direct_row.pair_accuracy.value`), 3)}, 2024년 같은 조사 원자료 집계는 {fixed(num(`${RANK_SET}.krei_2024.spearman.value`), 3)}, {fixed(num(`${RANK_SET}.krei_2024.pair_accuracy.value`), 3)}였습니다.
      </p>
      <div className="figure">
        <div className="figure-title">Spearman 순위 상관, 95% 구간</div>
        <Legend
          items={[
            { label: "패널", fill: COLOR.panel },
            { label: "실제 200명", fill: COLOR.real },
            { label: "2024 원자료 집계", fill: COLOR.reference },
          ]}
        />
        <DotRows ariaLabel="순위 상관" rows={rankRows("spearman", 3)} domain={[0.3, 1]} ticks={[0.4, 0.6, 0.8, 1]} axisLabel="Spearman" />
      </div>
      <div className="figure">
        <div className="figure-title">쌍 정확도, 95% 구간</div>
        <DotRows ariaLabel="쌍 정확도" rows={rankRows("pair_accuracy", 3)} domain={[0.5, 1]} ticks={[0.5, 0.6, 0.7, 0.8, 0.9, 1]} axisLabel="쌍 정확도" />
      </div>
      <h4>쌍 차이</h4>
      <div className="table-wrap" tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th>비교</th>
              <th className="num">Spearman 차이</th>
              <th className="num">쌍 정확도 차이</th>
            </tr>
          </thead>
          <tbody>
            {[
              { k: "panel_C2_minus_krei_2024", label: "Terra C2 - 2024 집계" },
              { k: "panel_C2_minus_direct_row", label: "Terra C2 - 200명 row" },
              { k: "panel_C2_minus_direct_cluster", label: "Terra C2 - 200명 cluster" },
            ].map((r) => (
              <tr key={r.k}>
                <td>{r.label}</td>
                <td className="num">
                  {signed(num(`${RANK_SET}.${r.k}.spearman.mean_diff`), 3)} {ciText(interval(`${RANK_SET}.${r.k}.spearman.ci95`), 3)}
                </td>
                <td className="num">
                  {signed(num(`${RANK_SET}.${r.k}.pair_accuracy.mean_diff`), 3)} {ciText(interval(`${RANK_SET}.${r.k}.pair_accuracy.ci95`), 3)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h4>실제 차이 구간별 쌍 정확도</h4>
      <div className="table-wrap" tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th>실제 차이</th>
              <th className="num">Terra C2 (쌍 수)</th>
              <th className="num">200명 row</th>
              <th className="num">2024 집계</th>
            </tr>
          </thead>
          <tbody>
            {BANDS.map((b) => (
              <tr key={b.id}>
                <td>{b.label}</td>
                <td className="num">
                  {fixed(num(`ranking.bands.panel_C2.true_gap.${b.id}.accuracy`), 3)} ({num(`ranking.bands.panel_C2.true_gap.${b.id}.n_pairs`)})
                </td>
                <td className="num">{fixed(num(`ranking.bands.direct_row.true_gap.${b.id}.accuracy`), 3)}</td>
                <td className="num">{fixed(num(`ranking.bands.krei_2024.true_gap.${b.id}.accuracy`), 3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small">순서 시험의 고정 판정은 truth와 똑같은 추정치도 3~5pp와 5pp 이상 구간에서 넘지 못하므로 변별 근거로 쓰지 않습니다. 근거는 위 쌍 차이입니다.</p>
      <Caveats items={[...new Set([...caveats([`${RANK_SET}.panel_C2.spearman.value`, "ranking.bands.panel_C2.true_gap.5pp_and_over.accuracy"]), ...caveatsOf(["ranking.ceiling."])])]} />
      <SourceLine files={sources([`${RANK_SET}.panel_C2.spearman.value`])} keys="ranking.*" />
        </Evidence>
      </Scene>

      <Scene id="gender">
        <h2>제로 음료 경험의 성별 차이는 방향이 반대입니다</h2>
        <p className="say">
          실제는 여성이 {everGap.real.toFixed(1)}%⁠포인트 높게 나왔지만 그 구간은 0을 포함합니다. 패널은 여성이 {Math.abs(everGap.panel).toFixed(1)}%⁠포인트 낮게 답했고, 탄산 1순위는 방향이 같습니다.
        </p>
        <div className="chart-narrow">
          <GenderDumbbell
            rows={genderData}
            label={`성별 차이, 여성에서 남성을 뺀 %⁠포인트와 95% 구간. ${genderData.map((r) => `${r.label}: 실제 ${signed(r.real, 1)} [${r.realCi[0].toFixed(1)}, ${r.realCi[1].toFixed(1)}]${r.zeroInReal ? ", 구간이 0을 포함" : ""}, 패널 ${signed(r.panel, 1)} [${r.panelCi[0].toFixed(1)}, ${r.panelCi[1].toFixed(1)}]${r.opposite ? ", 방향 반대" : ""}`).join(". ")}.`}
          />
          <p className="small" style={{ maxWidth: "46em" }}>
            실제 구간이 0을 포함하는 항목은 {genderData.filter((r) => r.zeroInReal).map((r) => r.label).join(", ")}이고, {genderData.filter((r) => !r.zeroInReal).map((r) => r.label).join(", ")}는 포함하지 않습니다. 보라색은 방향이 반대인 항목입니다.
          </p>
        </div>
        <Evidence summary="성별 차이 표 보기">
          <Glossary />
          <p className="small">그림의 패널 구간은 results/main/main_score.json의 값으로 Terra C2 패널 안의 구간입니다. 표의 마지막 열은 패널에서 실제를 뺀 값의 구간입니다.</p>
      <h3>4. 성별 차이: 패널과 실제</h3>
      <p>패널의 ever 성별 차이는 {signed(num("stage2.stereotype.ever.terra_C2.gender_gap_pp"))}pp, 실제는 {signed(num("stage2.stereotype.ever.real_gender_gap_pp"))}pp입니다. 실제 값의 구간은 0을 포함합니다. ever와 weekly에서 패널과 실제의 차이 구간은 0을 제외하고, carb에서는 0을 포함합니다(Terra C2).</p>
        <details>
          <summary>표로 보기</summary>
          <div className="table-wrap" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>항목</th>
                  <th className="num">실제</th>
                  <th>조합</th>
                  <th className="num">패널</th>
                  <th className="num">패널 - 실제 구간</th>
                </tr>
              </thead>
              <tbody>
                {ITEMS.flatMap((i) =>
                  COMBOS.map((c) => (
                    <tr key={i.id + c.id}>
                      <td>{i.id}</td>
                      <td className="num">
                        {signed(num(`stage2.stereotype.${i.id}.real_gender_gap_pp`), 3)} {ciText(interval(`stage2.stereotype.${i.id}.real_gender_gap_ci95`), 3)}
                      </td>
                      <td>{c.label}</td>
                      <td className="num">{signed(num(`stage2.stereotype.${i.id}.${c.id}.gender_gap_pp`), 3)}</td>
                      <td className="num">{ciText(interval(`stage2.stereotype.${i.id}.${c.id}.gap_minus_real_ci95`), 3)}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
        </details>
      <Caveats items={caveats(genderKeys)} />
      <SourceLine files={sources(genderKeys)} keys="stage2.stereotype.*" />
        </Evidence>
      </Scene>

      <Scene tone="mist" id="person">
        <h2>사람 한 명씩 맞히는 힘은 제로 음료 경험만 바닥을 넘었습니다</h2>
        <p className="say">바닥은 나이와 성별만 쓴 모델입니다. 주 1회 이상과 탄산 1순위는 차이가 있다고 말할 수 없었습니다.</p>
        <div className="chart-narrow">
          <Key
            items={[
              { label: "GPT 패널", color: COLOR.panel, shape: "dot" },
              { label: "나이·성별 바닥", color: COLOR.reference, shape: "dot" },
            ]}
          />
          <DotRows ariaLabel={`개인 수준 AUC, 패널과 나이·성별 바닥. ${aucRows.map((r) => `${r.label} ${r.value}`).join(", ")}.`} rows={aucRows} domain={[0.5, 0.85]} ticks={[0.5, 0.6, 0.7, 0.8]} axisLabel="AUC" />
        </div>
        <Evidence summary="AUC 표 보기">
          <Glossary />
      <h3>6. 개인 수준: 연령·성별 바닥과의 AUC 차이</h3>
      <p>
        개인 수준에서는 Terra C2 ever만 Holm 보정 후 floor를 넘었고({signed(num("stage2.person.ever.terra_C2.auc_minus_floor"), 4)}, Holm p {num("stage2.person.ever.terra_C2.holm_p")}), weekly와 carb는 기각되지 않았습니다.
      </p>
      <div className="table-wrap" tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th>항목</th>
              <th className="num">Terra C2 AUC</th>
              <th className="num">floor AUC</th>
              <th className="num">차이 [95% 구간]</th>
              <th className="num">Holm p</th>
            </tr>
          </thead>
          <tbody>
            {ITEMS.map((i) => (
              <tr key={i.id}>
                <td>{i.id}</td>
                <td className="num">{fixed(num(`stage2.person.${i.id}.terra_C2.auc`), 4)}</td>
                <td className="num">{fixed(num(`stage2.person.${i.id}.floor_auc`), 4)}</td>
                <td className="num">
                  {signed(num(`stage2.person.${i.id}.terra_C2.auc_minus_floor`), 4)} {ciText(interval(`stage2.person.${i.id}.terra_C2.diff_ci95`), 4)}
                </td>
                <td className="num">{num(`stage2.person.${i.id}.terra_C2.holm_p`)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Caveats items={caveats(["stage2.person.ever.terra_C2.auc_minus_floor"])} />
      <SourceLine files={sources(["stage2.person.ever.terra_C2.auc_minus_floor"])} keys="stage2.person.*" />
        </Evidence>
      </Scene>

      <Scene tone="glass" id="duel">
        <h2>대결 결과는 나누는 방식에 흔들려 건강검진으로만 씁니다</h2>
        <p className="say">
          같은 표본에서 교차 검증을 나누는 방식만 바꿔도 추출의 {fixed(num("stage4.posthoc.same_sample.all_draws.terra_C2.share_draws_decision_changes") * 100, 1)}%에서 결정이 바뀌었습니다. 패널 값은 기본으로 보고서에서 빼고, 이 결정은 결과를 본 뒤에 정한 사후 결정입니다.
        </p>
        <div className="chart-narrow">
          <DotRows
            ariaLabel={`패널 값을 남기는 쪽으로 나온 비율. ${keepRows.filter((r) => r.label).map((r) => `${r.label} ${r.value}`).join(", ")}. 사전 기준은 대체 패널 ${stage4.duel_bar.surrogate_max_keep} 이하입니다.`}
            rows={keepRows}
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            refs={[{ x: stage4.duel_bar.surrogate_max_keep, label: `대체 패널 기준 ${stage4.duel_bar.surrogate_max_keep}` }]}
            axisLabel="패널 값을 남기는 쪽으로 나온 비율 (200회 추출)"
          />
        </div>
        <p className="small" style={{ maxWidth: "46em" }}>
          이 비율이 높아도 패널 값이 시장 수치라는 뜻은 아니고, 보고서에 들어간다는 뜻도 아닙니다. 앵커 문항에서 잰 값이고, 건강검진은 실제 설문을 만난 적이 없습니다.
        </p>
        <div className="rules">
          <h3>규칙 세 개 모두 제품 라벨로 쓰지 않습니다</h3>
          <p className="small" style={{ maxWidth: "46em" }}>
            v1은 미리 고정했고, v2와 v3는 답을 본 뒤에 썼습니다. 응답자 본인의 답을 넣은 패널도 v2를 넘지 못해 LLM 실패의 증거로 읽지 않습니다.
          </p>
          <div className="rule-key">
            {Object.entries(RULE_COLOR).map(([name, style]) => (
              <span key={name}>
                <i style={style.hollow ? { boxShadow: `inset 0 0 0 2px ${style.color}` } : { background: style.color }} />
                {name}
              </span>
            ))}
          </div>
          <div className="table-wrap">
            <table className="stack">
              <thead>
                <tr>
                  <th>패널</th>
                  <th>규칙 v1</th>
                  <th>규칙 v2</th>
                  <th>규칙 v3</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>
                    <strong>GPT 패널</strong>
                  </td>
                  {ruleCell("verdict.llm", "v1")}
                  {ruleCell("verdict.llm", "v2")}
                  {ruleCell("verdict.llm", "v3")}
                </tr>
                <tr>
                  <td>
                    <strong>실제 답을 넣은 대조군</strong>
                  </td>
                  {ruleCell("verdict.real_answers", "v1")}
                  {ruleCell("verdict.real_answers", "v2")}
                  {ruleCell("verdict.real_answers", "v3")}
                </tr>
                <tr>
                  <td>
                    <strong>LLM이 아닌 대체 패널</strong>
                  </td>
                  {ruleCell("verdict.surrogate", "v1")}
                  {ruleCell("verdict.surrogate", "v2")}
                  {ruleCell("verdict.surrogate", "v3")}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <Evidence summary="건강검진 결정, 동결 기록, 시드 민감도, 칸 판정 전체 보기">
          <Glossary />
      <h3 id="stage4-plan">4단계를 읽기 전에</h3>
      <p>
        아래 7~9절은 저장된 답으로 계산했고 새 페르소나 호출은 {num("spend.stage4.panel_calls")}건입니다. 계획과 측정 코드는 계산 전에 커밋하고 해시로 고정했습니다(config/prereg_stage4.json, manifests/frozen_stage4.json). 앞 단계 답과 결과, 시험 truth를 모두 본 뒤에 고정했으므로 눈가림 시험이 아닙니다. 사전 기준의 수치(약 10%를 0.12로, 양성 대조 s=1.0 등)도 고정 전에 스스로 정한 해석입니다. 다중 비교 보정은 없습니다. 「사후 계산」으로 표시한 값은 동결 결과를 본 뒤에 계산한 것입니다.
      </p>
      <h3>9. 대결 규칙: 건강검진으로 씁니다</h3>
      <HealthCheckDecision />
      <p>
        대결은 실제 200명 안의 5겹 교차 검증에서 보정 패널과 R1의 로그 손실을 비교하고, 평균 개선 구간 전체가 0 위이면 keep, 아니면 drop입니다. keep이어도 패널 값을 보고서에 넣지 않습니다. 이 절은 답이 있는 KREI 자료에서 그 규칙이 믿을 만한지 잰 값입니다. 앵커 문항에서 잰 값이고 콘셉트 문항 대결은 실제 설문을 만난 적이 없습니다.
      </p>
      <p>
        <strong>동결 기록:</strong> 사전 기준은 대체 패널 keep rate {stage4.duel_bar.surrogate_max_keep} 이하, 양성 대조와의 차이 {stage4.duel_bar.positive_min_margin} 이상입니다. 동결 시드에서는 넘었습니다(대체 패널 {num("stage4.duel.acceptance.surrogate_terra_slot.keep_rate")}, {fixed(num("stage4.duel.acceptance.surrogate_luna_slot.keep_rate"), 1)}, 양성 대조 {fixed(num("stage4.duel.acceptance.positive_keep_rate"), 1)}, 차이 {num("stage4.duel.acceptance.margin")} {ciText(interval("stage4.duel.acceptance.margin_ci95"), 2, false)}). 넘은 폭은 {fixed(stage4.duel_bar.surrogate_max_keep - num("stage4.duel.acceptance.surrogate_terra_slot.keep_rate"), 3)}이고, 기준 {stage4.duel_bar.surrogate_max_keep}는 「약 10%」를 고정 전에 작업자가 해석한 값입니다. 동결 결과를 본 뒤 돌린 다른 시드 {SEED_RUNS.length}개 중 {seedRunsFailed()}개에서 대체 패널 keep rate가 기준을 넘었습니다. 시드가 적어 비율로 읽지 않고, 기준 근처에서 시드에 따라 갈린다는 뜻으로 읽습니다. 라벨 <code>{any<string>("stage4.duel.acceptance.label")}</code>은 기록으로 남기되 확정 판정으로 읽지 않습니다.
      </p>
      <p>
        <strong>칸 오차 불일치:</strong> Terra C2 수준의 신호에서는 추출마다의 keep과 칸 오차 결과가 거의 맞물리지 않습니다. keep인 추출이 R1을 칸 오차로 이긴 비율은 {num(`${duelT}.count.kept_and_beats`)}/{num(`${duelT}.count.kept_and_beats`) + num(`${duelT}.count.kept_not_beats`)}, drop인 추출은 {num(`${duelT}.count.dropped_and_beats`)}/{num(`${duelT}.count.dropped_and_beats`) + num(`${duelT}.count.dropped_not_beats`)}입니다. 대결은 개인 로그 손실을, 이 점검은 칸 오차를 보므로 이 불일치는 대결의 오류율이 아닙니다.
      </p>
      <h4>keep과 칸 오차의 맞물림 (패널 밖 truth, 200회)</h4>
      <div className="table-wrap" tabIndex={0}>
        <table className="lead-col">
          <thead>
            <tr>
              <th>패널</th>
              <th className="num">keep rate</th>
              <th className="num">R1을 이긴 비율</th>
              <th className="num">keep·이김</th>
              <th className="num">keep·못 이김</th>
              <th className="num">drop·이김</th>
              <th className="num">drop·못 이김</th>
              <th className="num">불일치: keep 중 못 이김</th>
              <th className="num">불일치: 이긴 것 중 drop</th>
              <th className="num">평균 개선</th>
            </tr>
          </thead>
          <tbody>
            {DUEL_PANELS.map((p) => {
              const top = `stage4.duel.row.${p.id}.pooled`;
              const base = `${top}.panel_excluded`;
              return (
                <tr key={p.id}>
                  <td>{p.label}</td>
                  <td className="num">{fixed(num(`${base}.keep_rate`), 3)}</td>
                  <td className="num">{fixed(num(`${base}.beats_rate`), 3)}</td>
                  <td className="num">{num(`${base}.count.kept_and_beats`)}</td>
                  <td className="num">{num(`${base}.count.kept_not_beats`)}</td>
                  <td className="num">{num(`${base}.count.dropped_and_beats`)}</td>
                  <td className="num">{num(`${base}.count.dropped_not_beats`)}</td>
                  <td className="num">{rateOrDash(`${base}.false_keep_rate`, 4)}</td>
                  <td className="num">{rateOrDash(`${base}.missed_keep_rate`, 4)}</td>
                  <td className="num">{signed(num(`${top}.mean_improvement`), 5)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <details>
        <summary>항목별 keep rate와 cluster 추출 민감도 보기</summary>
        <div className="table-wrap" tabIndex={0}>
          <table className="lead-col">
            <thead>
              <tr>
                <th>패널</th>
                <th className="num">ever</th>
                <th className="num">weekly</th>
                <th className="num">carb</th>
                <th className="num">통합, cluster 추출 (사전 기준에서 읽지 않음)</th>
              </tr>
            </thead>
            <tbody>
              {DUEL_PANELS.map((p) => (
                <tr key={p.id}>
                  <td>{p.label}</td>
                  {ITEMS.map((i) => (
                    <td className="num" key={i.id}>
                      {fixed(num(`stage4.duel.row.${p.id}.${i.id}.panel_excluded.keep_rate`), 3)}
                    </td>
                  ))}
                  <td className="num">{fixed(num(`stage4.duel.cluster.${p.id}.pooled.panel_excluded.keep_rate`), 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <h4>시드 민감도 (동결 결과를 본 뒤 실행, 규칙과 라벨을 바꾸지 않음)</h4>
      <div className="table-wrap" tabIndex={0}>
        <table className="lead-col">
          <thead>
            <tr>
              <th>실행</th>
              <th>사전 기준</th>
              <th className="num">Terra C2</th>
              <th className="num">Luna C1</th>
              <th className="num">양성 대조 s=1.0</th>
              <th className="num">대체 패널, Terra 자리</th>
              <th className="num">대체 패널, Luna 자리</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>동결 시드</td>
              <td>{bool("stage4.duel.acceptance.passed") ? "통과" : "탈락"}</td>
              <td className="num">{fixed(num("stage4.duel.row.terra_C2.pooled.panel_excluded.keep_rate"), 3)}</td>
              <td className="num">{fixed(num("stage4.duel.row.luna_C1.pooled.panel_excluded.keep_rate"), 3)}</td>
              <td className="num">{fixed(num("stage4.duel.acceptance.positive_keep_rate"), 3)}</td>
              <td className="num">{fixed(num("stage4.duel.acceptance.surrogate_terra_slot.keep_rate"), 3)}</td>
              <td className="num">{fixed(num("stage4.duel.acceptance.surrogate_luna_slot.keep_rate"), 3)}</td>
            </tr>
            {SEED_RUNS.map((run) => {
              const base = `stage4.duel.seed.${run}`;
              return (
                <tr key={run}>
                  <td>
                    <code>{run}</code>
                  </td>
                  <td>{bool(`${base}.acceptance_passed`) ? "통과" : "탈락"}</td>
                  <td className="num">{fixed(num(`${base}.terra_C2.keep_rate`), 3)}</td>
                  <td className="num">{fixed(num(`${base}.luna_C1.keep_rate`), 3)}</td>
                  <td className="num">{fixed(num(`${base}.control_s1.0.keep_rate`), 3)}</td>
                  <td className="num">{fixed(num(`${base}.surrogate_terra_slot.keep_rate`), 3)}</td>
                  <td className="num">{fixed(num(`${base}.surrogate_luna_slot.keep_rate`), 3)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h4 id="post-hoc">사후 계산: 같은 규칙, 동결 추출과 접힘 시드</h4>
      <p className="small">아래 세 표는 동결 결과를 본 뒤에 계산했습니다. 사전 기준과 동결 라벨을 대체하지 않습니다. 시연 패널 조건은 C1이고, LLM 없는 floor는 학습 분할로 맞춘 나이·성별 모델입니다.</p>
      <div className="table-wrap" tabIndex={0}>
        <table className="lead-col">
          <thead>
            <tr>
              <th>패널</th>
              <th className="num">keep rate [구간]</th>
              <th className="num">패널 밖 truth 칸 오차로 R1을 이긴 비율</th>
              <th className="num">draw 0, 동결 접힘 시드</th>
            </tr>
          </thead>
          <tbody>
            {[
              { label: "Terra C2 (동결 파일과 같음)", base: `stage4.duel.row.terra_C2.pooled.panel_excluded`, draw: "terra_C2" },
              { label: "Terra C1 (시연 조건)", base: "stage4.posthoc.row.terra_C1", draw: "terra_C1" },
              { label: "LLM 없는 floor", base: "stage4.posthoc.row.floor_no_llm", draw: "floor_no_llm" },
            ].map((r) => (
              <tr key={r.draw}>
                <td>{r.label}</td>
                <td className="num">
                  {fixed(num(`${r.base}.keep_rate`), 3)} {ciText(interval(`${r.base}.keep_rate_ci95`), 3, false)}
                </td>
                <td className="num">{fixed(num(`${r.base}.beats_rate`), 3)}</td>
                <td className="num">{bool(`stage4.posthoc.draw0_keep_at_frozen_fold_seed.${r.draw}`) ? "keep" : "drop"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h4 id="unit-intact">사후 계산: 조사 단위를 온전히 둔 접힘의 keep rate</h4>
      <div className="table-wrap" tabIndex={0}>
        <table className="lead-col">
          <thead>
            <tr>
              <th>패널</th>
              <th className="num">row 추출, 평균 [범위]</th>
              <th className="num">cluster 추출, 평균 [범위]</th>
            </tr>
          </thead>
          <tbody>
            {[
              { id: "terra_C2", label: "Terra C2" },
              { id: "terra_C1", label: "Terra C1" },
              { id: "luna_C1", label: "Luna C1" },
              { id: "surrogate_terra_slot", label: "대체 패널, Terra 자리" },
              { id: "floor_no_llm", label: "LLM 없는 floor" },
              { id: "control_s1.0", label: "양성 대조 s=1.0" },
              { id: "control_s0.25", label: "양성 대조 s=0.25" },
            ].map((r) => (
              <tr key={r.id}>
                <td>{r.label}</td>
                {["row", "cluster"].map((kind) => (
                  <td className="num" key={kind}>
                    {fixed(num(`stage4.posthoc.unit_intact.${kind}.${r.id}.keep_rate_mean`), 3)} {ciText(interval(`stage4.posthoc.unit_intact.${kind}.${r.id}.keep_rate_range`), 3, false)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small">접힘 시드 {num("stage4.posthoc.unit_intact.row.fold_seeds")}개 평균입니다. 이 접힘에서 Terra C2와 대체 패널은 구별되지 않습니다. 양성 대조의 keep rate는 유지되므로 규칙이 이 접힘에서 신호를 못 보는 것은 아닙니다.</p>
      <h4 id="same-sample">사후 계산: 같은 표본에서 접힘 시드만 바꾸면</h4>
      <div className="table-wrap" tabIndex={0}>
        <table className="lead-col">
          <thead>
            <tr>
              <th>패널</th>
              <th className="num">draw 0 keep 비율</th>
              <th className="num">결정이 바뀌는 추출</th>
              <th className="num">keep 비율 25~75% 추출</th>
              <th className="num">draw 0 ever, weekly, carb</th>
            </tr>
          </thead>
          <tbody>
            {[
              { id: "terra_C2", label: "Terra C2" },
              { id: "terra_C1", label: "Terra C1" },
              { id: "surrogate_terra_slot", label: "대체 패널, Terra 자리" },
            ].map((r) => {
              const draw = `stage4.posthoc.same_sample.draw0.${r.id}`;
              const all = `stage4.posthoc.same_sample.all_draws.${r.id}`;
              return (
                <tr key={r.id}>
                  <td>{r.label}</td>
                  <td className="num">{fixed(num(`${draw}.pooled_keep_share`), 3)}</td>
                  <td className="num">{fixed(num(`${all}.share_draws_decision_changes`), 3)}</td>
                  <td className="num">{fixed(num(`${all}.share_draws_between_25_75`), 3)}</td>
                  <td className="num">
                    {fixed(num(`${draw}.ever.keep_share`), 3)}, {fixed(num(`${draw}.weekly.keep_share`), 3)}, {fixed(num(`${draw}.carb.keep_share`), 3)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="small">draw 0은 접힘 시드 {num("stage4.posthoc.same_sample.draw0.terra_C2.fold_seeds")}개 기준이고, 나머지 두 열은 200회 추출에 접힘 시드 {num("stage4.posthoc.same_sample.all_draws.terra_C2.fold_seeds_per_draw")}개씩 적용한 비율입니다. 항목별 차이가 커서 한 번의 항목별 결과를 인용하지 않습니다.</p>
      <p className="small">
        경로가 어디까지 왔는지와 KREI 대용 실행은 <a href="/run#duel">실행 기록</a>에 있습니다. 실제 설문에 대결을 쓰려면 반복 접힘, 조사 단위를 온전히 둔 접힘, Terra C1, LLM 없는 floor, 상수 패널을 넣은 새 사전 등록을 계산 전에 커밋해야 합니다. 동결 계획은 고치지 않습니다.
      </p>
      <Caveats items={caveats(["stage4.duel.acceptance.passed", "stage4.duel.acceptance.label", "stage4.duel.seed.fold_seed_99.acceptance_passed", "stage4.posthoc.row.terra_C1.keep_rate", "stage4.policy.default"])} />
      <SourceLine files={sources(["stage4.duel.acceptance.passed", "stage4.duel.seed.fold_seed_99.acceptance_passed", "stage4.posthoc.row.terra_C1.keep_rate"])} keys="stage4.duel.*, stage4.posthoc.*" />
      <h3>5. 칸 판정: 규칙 v1, v2, v3</h3>
      <p>
        규칙 v2와 v3는 2단계 답을 본 뒤에 썼으므로 그 답에 대해 사전 등록이 아닙니다. 아래 판정은 어느 것도 제품 라벨이 아닙니다(<code>product_labels_allowed: {String(bool("verdict.v3.product_labels_allowed"))}</code>).
      </p>
      <div className="table-wrap" tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th>패널</th>
              <th>규칙 v1</th>
              <th>규칙 v2</th>
              <th>규칙 v3</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>LLM 12개</td>
              <td>보정 후 참고 {num(`${v3}.v1.count.보정 후 참고`)}</td>
              <td>
                방향만 {num(`${v3}.v2.count.방향만`)}, 실측 전용 {num(`${v3}.v2.count.실측 전용`)}
              </td>
              <td>
                방향만 {num(`${v3}.v3.count.방향만`)}, 판정 불가 {num(`${v3}.v3.count.판정 불가`)}
              </td>
            </tr>
            <tr>
              <td>실제 답 대조군 (4칸이 같은 결과)</td>
              <td>보정 후 참고 {num("verdict.real_answers.v1.count.보정 후 참고")}</td>
              <td>
                방향만 {num("verdict.real_answers.v2.count.방향만")}, 실측 전용 {num("verdict.real_answers.v2.count.실측 전용")}
              </td>
              <td>
                보정 후 참고 {num("verdict.real_answers.v3.count.보정 후 참고")}, 방향만 {num("verdict.real_answers.v3.count.방향만")}
              </td>
            </tr>
            <tr>
              <td>LLM이 아닌 대체 패널</td>
              <td>
                보정 후 참고 {num("verdict.surrogate.v1.count.보정 후 참고")}, 방향만 {num("verdict.surrogate.v1.count.방향만")}
              </td>
              <td>
                방향만 {num("verdict.surrogate.v2.count.방향만")}, 실측 전용 {num("verdict.surrogate.v2.count.실측 전용")}
              </td>
              <td>
                방향만 {num("verdict.surrogate.v3.count.방향만")}, 실측 전용 {num("verdict.surrogate.v3.count.실측 전용")}, 판정 불가 {num("verdict.surrogate.v3.count.판정 불가")}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <ul>
        <li>R1을 row와 cluster 모두에서 이긴 조합은 0개입니다. 다만 응답자 본인의 실제 답을 넣은 패널도 규칙 v2에서 통과하지 못해, 이 결과를 LLM 실패의 증거로 읽을 수 없습니다.</li>
        <li>규칙 v3의 첫 분기는 실제 답에 가까운 패널에서만 작동합니다. LLM의 보정 후 참고 0개를 LLM 실패의 증거로 읽지 않고, 규칙이 LLM을 가려낸다고 읽지도 않습니다.</li>
        <li>carb의 실측 전용은 실측 기울기 구간이 0을 포함해서 규칙으로 정해지며, 실제 답을 넣은 패널도 규칙 v2에서 같은 라벨을 받습니다. 패널이 탄산을 못 맞혔다는 뜻이 아닙니다.</li>
        <li>성별 차이 사용 금지 플래그는 구간 경계에 있어 시드에 따라 변합니다(세 시드에서 12개 중 {num("verdict.gender_flag.count.alt_seed_20261102")}~{num("verdict.gender_flag.count.stage2_seed")}개). 정확한 개수로 쓰지 않습니다.</li>
      </ul>
      <details>
        <summary>LLM 12개와 실제 답 대조군, 행별 표 보기</summary>
        <div className="table-wrap" tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th>항목</th>
                <th>조합</th>
                <th>v1</th>
                <th>v2</th>
                <th>v3</th>
                <th className="num">E4 - R1 row (패널 밖 truth)</th>
                <th className="num">cluster 평균</th>
              </tr>
            </thead>
            <tbody>
              {verdictCombos.map(({ c, i }) => {
                const base = `verdict.llm.${c.id}.${i.id}`;
                const labels = any<{ v1: string; v2: string; v3: string }>(`${base}.labels`);
                return (
                  <tr key={base}>
                    <td>{i.id}</td>
                    <td>{c.label}</td>
                    <td>{labels.v1}</td>
                    <td>{labels.v2}</td>
                    <td>{labels.v3}</td>
                    <td className="num">
                      {signed(num(`${base}.E4_minus_R1_outside.row.mean_diff`))} {ciText(interval(`${base}.E4_minus_R1_outside.row.ci95`))}
                    </td>
                    <td className="num">{signed(num(`${base}.E4_minus_R1_outside.cluster.mean_diff`))}</td>
                  </tr>
                );
              })}
              {ITEMS.map((i) => (
                <tr key={`real${i.id}`}>
                  <td>{i.id}</td>
                  <td>실제 답 대조군</td>
                  <td colSpan={3}>
                    {controls.real_answer_labels[i.id as "ever"].v1} / {controls.real_answer_labels[i.id as "ever"].v2} / {controls.real_answer_labels[i.id as "ever"].v3}
                  </td>
                  <td className="num">
                    {signed(num(`verdict.real_answers.${i.id}.E4_minus_R1.row.mean_diff`))} {ciText(interval(`verdict.real_answers.${i.id}.E4_minus_R1.row.ci95`))}
                  </td>
                  <td className="num">{signed(num(`verdict.real_answers.${i.id}.E4_minus_R1.cluster.mean_diff`))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <Caveats items={caveats(["verdict.llm.terra_C2.ever.labels", "verdict.v3.acceptance_passed", "verdict.gender_flag.count.stage2_seed"])} />
      <SourceLine files={sources(["verdict.llm.terra_C2.ever.labels", "verdict.v3.acceptance_passed"])} keys="verdict.*" />
        </Evidence>
      </Scene>

      <Scene tone="mist" id="tried">
        <h2>해 봤지만 효과가 없던 것</h2>
        <p className="say">
          저장된 답으로 계산했고, 이 측정들의 새 페르소나 호출은 {num("spend.stage4.panel_calls")}건입니다. 에이전트 방어에서 뚫린 것은 <a href="/attacks">공격 기록</a>에 있습니다.
        </p>
        <div className="two-col">
          <div>
            <h3 id="allocation">패널로 200명을 나눠도 비례 배분과 차이가 없었습니다</h3>
            <p className="small">칸별 인원이 최대 {cellDiff}명만 달라 결과가 달라질 여지가 거의 없습니다. 미달을 패널 실패의 증거로 읽지는 않습니다.</p>
            <DotRows ariaLabel={`배분 방식별 칸 오차, 3항목 평균. ${allocRows.map((r) => `${r.label} ${r.value}`).join(", ")}.`} rows={allocRows} domain={[0, 8]} ticks={[0, 2, 4, 6, 8]} axisLabel="칸 오차, %⁠포인트" />
          </div>
          <div>
            <h3 id="flags">틀린 칸을 실측 전에 짚어 낸 증거가 없었습니다</h3>
            <p className="small">오차 상위 9칸과 겹친 칸 수가 모두 무작위 범위 안입니다. 이 시험은 검정력이 낮아, 신호가 쓸모없다는 증명은 아닙니다.</p>
            <Key
              items={[
                { label: "겹친 칸 수", color: COLOR.panel, shape: "dot" },
                { label: "무작위 평균과 95 범위", color: COLOR.reference },
              ]}
            />
            <DotRows ariaLabel={`신호별 오차 상위 9칸과의 겹침. ${flagRows.map((r) => `${r.label} ${r.value}`).join(", ")}. 무작위 95 범위 0에서 5입니다.`} rows={flagRows} domain={[0, 9]} ticks={[0, 3, 6, 9]} axisLabel="겹친 칸 수, 선은 무작위 95 범위" />
          </div>
        </div>
        <Evidence summary="배분 표, 칸별 인원, 신호 표 보기">
          <Glossary />
      <h3>7. 패널이 실측 200명 배분을 돕는가</h3>
      <p>
        비례 배분과 실질적 차이가 없었습니다. 패널 배분 - 비례 배분은 평균 {signed(num(`${ALLOC}.panel_neyman_minus_proportional.average.mean_diff`), 3)}pp(추출별 차이의 95% 범위 {ciText(interval(`${ALLOC}.panel_neyman_minus_proportional.average.ci95`), 3)}), 패널 배분 - reference 배분은 평균 {signed(num(`${ALLOC}.panel_minus_reference.average.mean_diff`), 3)}pp(범위 {ciText(interval(`${ALLOC}.panel_minus_reference.average.ci95`), 3)})입니다. 패널 배분과 비례 배분은 칸별로 최대 {cellDiff}명 차이여서 결과가 달라질 여지가 거의 없습니다. reference의 칸별 비율은 carb만 2024년 자료이고 ever와 weekly는 2025년 train 분할이어서, 패널에 불리한 비교입니다.
      </p>
      <p>
        동결 기준(범위 전체가 0 아래)은 둘 다 미달입니다(<code>panel_helps_over_proportional: {String(bool("stage4.allocation.reading.panel_helps_over_proportional"))}</code>, <code>panel_adds_over_reference: {String(bool("stage4.allocation.reading.panel_adds_over_reference"))}</code>). 이 범위는 평균의 신뢰구간이 아니라 추출 사이의 퍼짐이어서, 이 기준은 정답을 아는 oracle 배분도 넘지 못합니다(사후 검증 계산, 이 저장소의 결과 파일에는 없는 점검입니다). 미달을 패널 실패의 증거로 읽지 않고, 근거는 평균 차이의 크기로 봅니다.
      </p>
      <h4>R1, 패널 밖 truth, 칸 MAE (pp, 200회 추출 평균)</h4>
      <div className="table-wrap" tabIndex={0}>
        <table className="lead-col">
          <thead>
            <tr>
              <th>배분</th>
              {ALLOC_ITEMS.map((i) => (
                <th className="num" key={i}>
                  {i === "average" ? "3항목 평균" : i}
                </th>
              ))}
              <th className="num">평균 - 비례 [추출별 95% 범위]</th>
            </tr>
          </thead>
          <tbody>
            {DESIGNS.map((d) => (
              <tr key={d.id}>
                <td>{d.label}</td>
                {ALLOC_ITEMS.map((i) => (
                  <td className="num" key={i}>
                    {fixed(num(`${ALLOC}.${d.id}.${i}.mean`), 3)}
                  </td>
                ))}
                <td className="num">{d.id === "proportional" ? "기준" : `${signed(num(`${ALLOC}.${d.id}_minus_proportional.average.mean_diff`), 3)} ${ciText(interval(`${ALLOC}.${d.id}_minus_proportional.average.ci95`), 3)}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details>
        <summary>칸별 인원 보기</summary>
        <div className="table-wrap" tabIndex={0}>
          <table className="lead-col">
            <thead>
              <tr>
                <th>배분</th>
                {stage4.allocation.cell_names.map((c) => (
                  <th className="num" key={c}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                { key: "stage4.allocation.n_per_cell.equal", label: "균등" },
                { key: "stage4.allocation.n_per_cell.proportional", label: "비례" },
                { key: "stage4.allocation.n_per_cell.panel_neyman", label: "패널 Neyman" },
                { key: "stage4.allocation.n_per_cell.reference_neyman", label: "reference Neyman" },
                { key: "stage4.allocation.caps", label: "풀 상한" },
              ].map((row) => (
                <tr key={row.key}>
                  <td>{row.label}</td>
                  {any<number[]>(row.key).map((n, i) => (
                    <td className="num" key={i}>
                      {n}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="small">칸 이름의 앞자리는 연령대 코드, 뒷자리는 성별 코드입니다. 상한에 걸린 칸은 없습니다. reference는 carb에 a2024, ever와 weekly에 2025년 train 분할을 썼습니다. 문항 A19_1이 a2024에 없기 때문입니다.</p>
      </details>
      <details>
        <summary>다른 추정기와 truth로 본 3항목 평균 보기</summary>
        <div className="table-wrap" tabIndex={0}>
          <table className="lead-col">
            <thead>
              <tr>
                <th>추정기, truth, 지표</th>
                <th className="num">비례</th>
                <th className="num">패널 Neyman</th>
                <th className="num">패널 - 비례 [범위]</th>
                <th className="num">패널 - reference [범위]</th>
              </tr>
            </thead>
            <tbody>
              {ALLOC_COMBOS.map((c) => {
                const base = `stage4.allocation.${c.est}.${c.truth}.${c.metric}`;
                return (
                  <tr key={base}>
                    <td>{c.label}</td>
                    <td className="num">{fixed(num(`${base}.proportional.average.mean`), 3)}</td>
                    <td className="num">{fixed(num(`${base}.panel_neyman.average.mean`), 3)}</td>
                    <td className="num">
                      {signed(num(`${base}.panel_neyman_minus_proportional.average.mean_diff`), 3)} {ciText(interval(`${base}.panel_neyman_minus_proportional.average.ci95`), 3)}
                    </td>
                    <td className="num">
                      {signed(num(`${base}.panel_minus_reference.average.mean_diff`), 3)} {ciText(interval(`${base}.panel_minus_reference.average.ci95`), 3)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="small">이 표의 어느 행에서도 추출별 95% 범위가 0을 제외하지 않습니다.</p>
      </details>
      <Caveats items={caveats([`${ALLOC}.proportional.average.mean`, "stage4.allocation.reading.panel_helps_over_proportional"])} />
      <SourceLine files={sources([`${ALLOC}.proportional.average.mean`])} keys="stage4.allocation.*" />

      <h3>8. 패널이 실측 전에 틀린 칸을 지목하는가</h3>
      <p>
        지목의 증거가 나오지 않았습니다. 세 신호 중 사전 기준을 넘은 것은 {namedCount}개입니다. 두 모델이 갈리는 칸이 더 틀린 칸이라는 가설은 지지되지 않았습니다. 점추정 부호가 반대이고 구간이 0을 겨우 포함합니다. 오차 상위 9칸 겹침은 모두 무작위 95 범위 {ciText(stage4.flags_random_95.terra_minus_luna as [number, number], 0, false)} 안이고, 단측 p는 {fixed(Math.min(...namingSignals.map((s) => num(`stage4.flags.${s.id}.overlap_top9.p_one_sided`))), 2)} 이상입니다. 칸이 36개이고 칸마다 truth 응답자가 적어 이 신호 시험은 검정력이 낮습니다. 지목한다는 증거가 없다는 뜻이고, 신호가 쓸모없다는 증명은 아닙니다.
      </p>
      <div className="table-wrap" tabIndex={0}>
        <table className="lead-col">
          <thead>
            <tr>
              <th>신호 (Terra C2, 36개 항목·칸)</th>
              <th className="num">Spearman [구간]</th>
              <th className="num">항목 내 Spearman [구간]</th>
              <th className="num">상위 9칸 겹침 / 무작위 평균</th>
              <th className="num">p (단측)</th>
              <th className="num">시험 전체 truth의 Spearman</th>
              <th>지목</th>
            </tr>
          </thead>
          <tbody>
            {SIGNALS.map((s) => {
              const base = `stage4.flags.${s.id}`;
              return (
                <tr key={s.id}>
                  <td>{s.label}</td>
                  <td className="num">
                    {signed(num(`${base}.spearman`), 3)} {ciText(interval(`${base}.spearman_ci95`), 3)}
                  </td>
                  <td className="num">
                    {signed(num(`${base}.within_item_spearman`), 3)} {ciText(interval(`${base}.within_item_ci95`), 3)}
                  </td>
                  <td className="num">
                    {num(`${base}.overlap_top9.observed`)} / {fixed(num(`${base}.overlap_top9.random_mean`), 3)}
                  </td>
                  <td className="num">{fixed(num(`${base}.overlap_top9.p_one_sided`), 3)}</td>
                  <td className="num">{signed(num(`${base}.whole_test_truth.spearman`), 3)}</td>
                  <td>{has(`${base}.names_wrong_cells`) ? (bool(`${base}.names_wrong_cells`) ? "기준 넘음" : "기준 미달") : "비교용"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="small">
        칸 오차 크기: ever 평균 {fixed(num("stage4.flags.error.ever.mean_pp"), 3)}pp 최대 {fixed(num("stage4.flags.error.ever.max_pp"), 3)}pp, weekly 평균 {fixed(num("stage4.flags.error.weekly.mean_pp"), 3)}pp 최대 {fixed(num("stage4.flags.error.weekly.max_pp"), 3)}pp, carb 평균 {fixed(num("stage4.flags.error.carb.mean_pp"), 3)}pp 최대 {fixed(num("stage4.flags.error.carb.max_pp"), 3)}pp. 반복 응답 편차의 36칸 Spearman {signed(num("stage4.flags.repeat_sd.spearman"), 3)}은 항목 안으로 들어가면 {signed(num("stage4.flags.repeat_sd.within_item_spearman"), 3)}입니다. 항목 간 크기 차이의 영향으로 보이며 이것은 해석입니다.
      </p>
      <Caveats items={caveats(["stage4.flags.repeat_sd.spearman"])} />
      <SourceLine files={sources(["stage4.flags.repeat_sd.spearman"])} keys="stage4.flags.*" />
        </Evidence>
      </Scene>
    </>
  );
}
