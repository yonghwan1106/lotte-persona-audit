import Link from "next/link";
import { Caveats } from "@/components/Notes";
import { ActionTable, DetectableTable, DuelStatusTable, ExploreCard, HealthCheckDecision, HealthCheckReasons, OrderNotes, seedRunsFailed, SEED_RUNS } from "@/components/Stage4";
import { ErrorLadder, type LadderStep } from "@/components/viz/Charts";
import { FlowLine, FlowTable } from "@/components/viz/FlowLine";
import { HeroGlasses, type GlassItem } from "@/components/viz/HeroGlasses";
import { ReportGate } from "@/components/viz/ReportGate";
import { SampleSlider } from "@/components/viz/SampleSlider";
import { Evidence, Figure, Glossary, Scene } from "@/components/viz/Scene";
import { Vessel } from "@/components/viz/Vessel";
import demo from "@/data/demo.json";
import stage4 from "@/data/stage4.json";
import { COLOR } from "@/lib/colors";
import { halfUp } from "@/lib/format";
import { any, bool, caveats, ciText, fixed, interval, num, signed, str, usd } from "@/lib/numbers";

type Row = { what: string; state: string; ok: boolean; scope: React.ReactNode };

function cardSummary(id: string) {
  const card = demo.cards.find((c) => c.id === id);
  if (!card) throw new Error(`no card ${id}`);
  return { attributes: card.attributes.join(", "), price: card.price_band };
}

export default function HomePage() {
  const e4r = "stage2.n200.row.terra_C2.E4.average.minus_R1";
  const e4c = "stage2.n200.cluster.terra_C2.E4.average.minus_R1";
  const rank = "ranking.merged_coffee_15";
  const alloc = "stage4.allocation.R1.panel_excluded.cell_mae";
  const gate = stage4.gate_audit;
  const negatives = (["terra", "luna"] as const).flatMap((m) => ["A", "B", "C"].map((c) => num(`demo.${m}.negative.${c}.mean`)));
  const proportional = any<number[]>("stage4.allocation.n_per_cell.proportional");
  const cellDiff = Math.max(...any<number[]>("stage4.allocation.n_per_cell.panel_neyman").map((n, i) => Math.abs(n - proportional[i])));

  const glass = (id: string, label: string): GlassItem => {
    const real = num(`stage2.stereotype.${id}.real_national_pct`);
    return { id, label, real, panel: real + num(`stage2.stereotype.${id}.terra_C2.bias_pp`) };
  };
  const glasses = [glass("ever", "제로 음료 경험"), glass("weekly", "제로 음료 주 1회 이상"), glass("carb", "탄산 1순위")];

  const ladder: LadderStep[] = [
    { id: "E3", label: "패널 그대로", note: "실제 응답 없이 패널 값만", value: Number(fixed(num("stage2.n200.row.terra_C2.E3.average.cell_mae"), 1)), fill: COLOR.yuzu },
    { id: "E2", label: "실제 200명 평균", flag: "약한 비교 상대", note: "실제 200명을 전체 평균 쪽으로 줄인 값", value: Number(fixed(num("stage2.n200.row.E2.average.cell_mae"))), fill: COLOR.real },
    { id: "E4", label: "패널 보정", note: "패널을 실제 200명으로 맞춘 값", value: Number(fixed(num("stage2.n200.row.terra_C2.E4.average.cell_mae"))), fill: COLOR.real, tab: COLOR.yuzu },
    { id: "R1", label: "패널 없는 단순 통계", note: "같은 200명의 나이·성별 회귀", value: Number(fixed(num("stage2.n200.row.R1.average.cell_mae"))), fill: COLOR.real },
  ];
  const ladderGap = `차이 ${signed(num(`${e4r}.mean_diff`))}, 범위 ${ciText(interval(`${e4r}.ci95`))}`;

  const d = stage4.detectable;
  const marks = [
    { perCard: d.n_arm, total: d.n_total, gap: d.between_mde_pp },
    ...[...d.needed].reverse().map((row) => ({ perCard: row.between_per_arm, total: row.between_total, gap: row.gap_pp })),
  ];

  const totalSeconds = gate.seconds.terra_from_call_log + gate.seconds.luna;
  const health = stage4.real_results.health_check;
  const bubbles = [
    { card: "A", kind: "can" as const, line: stage4.explore.cards.A.sections.objections[0] },
    { card: "B", kind: "can" as const, line: stage4.explore.cards.B.sections.objections[1] },
    { card: "C", kind: "pet" as const, line: stage4.explore.cards.C.sections.objections[2] },
  ];
  const gapLow = fixed(Math.min(...negatives), 1);
  const gapHigh = fixed(Math.max(...negatives), 1);

  const verified: Row[] = [
    {
      what: "패널이 기존 음료 행동 3개 항목의 12칸을 얼마나 맞히는지",
      state: "측정함",
      ok: true,
      scope: "KREI 2025 시험 분할. 제로 음료 경험, 주 1회 이상, 1순위 탄산. 시험 truth는 앞 단계부터 본 값이어서 눈가림 시험이 아닙니다.",
    },
    {
      what: "패널에 실제 200명을 더한 추정과 같은 200명만 쓴 회귀의 비교",
      state: "측정함, 구별되지 않음",
      ok: true,
      scope: `Terra C2 E4 - R1: ${signed(num(`${e4r}.mean_diff`))}pp ${ciText(interval(`${e4r}.ci95`))}(row), ${signed(num(`${e4c}.mean_diff`))}pp ${ciText(interval(`${e4c}.ci95`))}(cluster). 구간은 추출 변동만 담습니다.`,
    },
    {
      what: "A15 음료 순서",
      state: "측정함, 패널이 낮음",
      ok: true,
      scope: `패널 밖 truth ${num("stage2.outside_truth_rows").toLocaleString("en-US")}행. 쌍 정확도 차이는 2024 집계 대비 ${signed(num(`${rank}.panel_C2_minus_krei_2024.pair_accuracy.mean_diff`))}, 200명 row 대비 ${signed(num(`${rank}.panel_C2_minus_direct_row.pair_accuracy.mean_diff`))}. 다중 비교 보정이 없습니다.`,
    },
    {
      what: "분할과 누출",
      state: "측정함",
      ok: true,
      scope: "응답자, 가구, 조사 단위는 분할을 넘지 않았고, 페르소나 3,264개에서 차단 패턴은 0건이었습니다.",
    },
    {
      what: "계획 고정 순서",
      state: "로그로 확인",
      ok: true,
      scope: `2단계 계획, 코드, 패널 해시는 첫 답 ${num("order.stage_2.seconds_from_freeze_to_first_answer")}초 전에 커밋되었습니다. 4단계 측정 계획과 코드는 계산 전에 커밋했습니다. 고정 전에 본 정보의 범위까지 증명하지는 않습니다. 규칙 v2, v3와 안별 제안 규칙은 답이나 시연 값을 본 뒤에 썼습니다.`,
    },
    {
      what: "감사 에이전트의 거절, 도구 순서, 승인, 예산",
      state: "시험한 형태 안에서",
      ok: true,
      scope: `시나리오 ${num("scenarios.fix_stage.passed")}/${num("scenarios.fix_stage.runs")}회 통과(조합당 3회). 이번 단계 문구로 조합당 1회 다시 돌린 첫 묶음은 ${num("stage4.scenarios.first_batch.passed")}/${num("stage4.scenarios.first_batch.runs")}이었고, 실패 7건은 실행기 연결 오류여서 고친 뒤 그 7건을 다시 돌려 ${num("stage4.scenarios.rerun_of_crashed.passed")}/${num("stage4.scenarios.rerun_of_crashed.runs")}입니다. 거절률 추정치가 아닙니다. 실제 API 공격에서 뚫린 것과 아직 통과하는 것은 공격 기록에 있습니다.`,
    },
    {
      what: "탐색 출력의 문장 필터",
      state: "시험한 형태 안에서",
      ok: true,
      scope: `합성 문장을 심는 시험 ${num("stage4.explore_filter.passed")}/${num("stage4.explore_filter.total")} 통과, API 호출 없음. 나열된 형태만 시험했고 시험하지 않은 표현은 통과할 수 있습니다.`,
    },
  ];
  const notVerified: Row[] = [
    { what: "새 콘셉트 반응의 정확도, 신제품 성패", state: "재지 않음", ok: false, scope: "기존 행동을 잘 맞혀도 새 콘셉트를 맞힌다는 뜻은 아닙니다. 시연의 구매 의향 값은 패널 내부 값이고 정답이 없습니다." },
    { what: "탈락 제안의 효용", state: "재지 않음", ok: false, scope: "공개 자료로 증명할 수 없습니다. 첫 시범의 되살림 검증으로 재야 합니다. 탈락 제안 기준 5pp는 기존 음료에서 나온 사후 가설입니다." },
    { what: "탐색 가설의 쓸모", state: "재지 않음", ok: false, scope: "LLM 출력이고 응답자의 말이 아닙니다. 실제 소비자에게 확인하지 않았습니다." },
    { what: "내부 콘셉트 테스트 대비 정확도", state: "재지 않음", ok: false, scope: "롯데칠성음료 내부 자료를 쓰지 않았습니다." },
    { what: "독립 표본 검증", state: "못 함", ok: false, scope: `시험 truth의 psfwt ${fixed(num("stage2.panel_share_of_test_psfwt"))}%가 패널 본인입니다. 패널 밖 truth로 다시 본 값은 측정 결과에 따로 있습니다.` },
    { what: "모집단 불확실성", state: "못 함", ok: false, scope: "2단계 구간은 보정 풀과 시험 패널을 고정한 채 추출만 반복한 값입니다." },
    { what: "사람 승인 화면", state: "없음", ok: false, scope: "시연 승인은 CLI 인자이고 사람이 하지 않았습니다. 사람이 터미널에서 이름과 계획 해시를 입력하는 명령이 있고, 작은 실행 한 번(human2)을 그렇게 승인했습니다. 입력한 사람이 누구인지 코드는 확인하지 못합니다." },
    { what: "조사 단위 군집 효과의 원인", state: "확인 못 함", ok: false, scope: "주 1회 항목은 정답 자체가 조사 단위 효과를 담을 수 있어 모델이 틀린 것과 조사가 흔들린 것을 완전히 가르지 못합니다." },
  ];

  const renderRow = (row: Row) => (
    <tr key={row.what}>
      <td>{row.what}</td>
      <td data-label="상태">
        <span className={row.ok ? "status wrap-ok" : "status no wrap-ok"}>{row.state}</span>
      </td>
      <td>{row.scope}</td>
    </tr>
  );

  const signals = ["terra_minus_luna", "c1_minus_c2", "repeat_sd"];
  const cite = [`stage2.stereotype.ever.terra_C2.bias_pp`, `${e4r}.mean_diff`, `${rank}.panel_C2.spearman.value`, "scenarios.fix_stage.passed", "stage4.scenarios.first_batch.runs", "stage4.explore_filter.total", "attacks.wf7.probe.kept_minus_clean_t2b_pp", "attacks.replay.live.total"];
  const tried: Row[] = [
    {
      what: "패널로 실제 200명을 더 잘 나눌 수 있는가",
      state: "실질적 차이 없음",
      ok: false,
      scope: `패널 배분과 비례 배분은 칸별로 최대 ${cellDiff}명 달랐고, 칸 오차 차이는 평균 ${signed(num(`${alloc}.panel_neyman_minus_proportional.average.mean_diff`), 3)}pp, 추출별 차이의 95% 범위 ${ciText(interval(`${alloc}.panel_neyman_minus_proportional.average.ci95`), 3)}입니다. 동결 기준은 ${bool("stage4.allocation.reading.panel_helps_over_proportional") ? "통과" : "미달"}이지만 이 기준은 정답을 아는 배분도 넘지 못해, 근거는 평균 차이의 크기로 봅니다.`,
    },
    {
      what: "실측 전에 틀린 칸을 집어내는가",
      state: "지목 증거 없음",
      ok: false,
      scope: `신호 ${signals.length}개 중 사전 기준을 넘은 것 ${signals.filter((s) => bool(`stage4.flags.${s}.names_wrong_cells`)).length}개. 칸이 36개이고 칸마다 truth 응답자가 적어 이 시험은 검정력이 낮습니다. 지목한다는 증거가 없다는 뜻이고, 신호가 쓸모없다는 증명은 아닙니다.`,
    },
    {
      what: "실측 뒤 패널 값을 남길지 정하는 판정 규칙",
      state: "건강검진으로 내림",
      ok: false,
      scope: `동결 시드에서 사전 기준을 넘었지만(양성 대조 keep rate ${fixed(num("stage4.duel.acceptance.positive_keep_rate"), 1)}, 대체 패널 ${num("stage4.duel.acceptance.surrogate_terra_slot.keep_rate")}), 동결 뒤 다른 시드 ${SEED_RUNS.length}개 중 ${seedRunsFailed()}개에서 기준을 넘지 못했고 같은 표본에서 접힘 시드만 바꿔도 결정이 뒤집힙니다. 패널을 검증하는 도구로 쓰지 않습니다.`,
    },
  ];

  return (
    <>
      <Scene className="hero">
        <h1>
          GPT 패널은 <span className="nb">제로 음료와 탄산을</span> 실제보다 높게 답합니다
        </h1>
        <HeroGlasses items={glasses} initial="weekly" />
        <div className="hero-copy">
          <p className="lead">패널은 GPT로 만든 가상 응답자입니다. 이 서비스는 콘셉트를 실제 200명 조사에 보내기 전에 패널로 안을 훑어 반대 이유와 문항 초안을 내고, 패널 절대값은 보고서 본문에 넣지 않으며, 결정은 담당자에게 남깁니다.</p>
          <div className="hero-links">
            <a href="#receive">담당자가 받는 것</a>
            <Link href="/results">측정 결과</Link>
          </div>
          <Evidence summary="유리잔 값 표와 이 서비스가 내는 것 보기">
            <div className="table-wrap" tabIndex={0}>
              <table>
                <thead>
                  <tr>
                    <th>항목</th>
                    <th className="num">실제 응답 %</th>
                    <th className="num">GPT 패널 %</th>
                    <th className="num">차이 %⁠포인트</th>
                  </tr>
                </thead>
                <tbody>
                  {glasses.map((g) => (
                    <tr key={g.id}>
                      <td>{g.label}</td>
                      <td className="num">{halfUp(g.real)}</td>
                      <td className="num">{halfUp(g.panel)}</td>
                      <td className="num">+{halfUp(g.panel - g.real)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <dl className="opening">
              <dt>무엇을 정하나</dt>
              <dd>라인 확장 후보를 고르는 초기 단계에서 어느 안을 실측 설문에 보낼지 정합니다. 고르는 사람은 담당자이고, 패널은 탈락을 확정하지 못합니다. 판매량과 신제품 성패는 예측하지 않습니다.</dd>
              <dt>무엇을 내나</dt>
              <dd>콘셉트 카드를 넣으면 합성 패널(LLM 페르소나)이 먼저 읽고, 안별 제안표(실측 후보 유지, 탈락 제안, 판단 불가와 이유), 반대 이유, 끌리는 점, 세그먼트 가설, 문항 초안, 실제 200명 배분표와 문항지를 냅니다. 설문은 보내지 않습니다.</dd>
              <dt>왜 필요한가</dt>
              <dd>
                실제 설문이 가를 수 있는 차이에는 한계가 있습니다. 200명을 두 안에 {num("stage4.detectable.n_arm")}명씩 나누면 실제 차이가 {num("stage4.detectable.between_mde_pp")}%⁠포인트보다 작을 때 가려내기 어려우므로, 설문에 넣을 안을 먼저 좁혀야 합니다. 그렇다고 패널 수치로 좁히면 안 됩니다. 기존 음료 행동에서 패널 원수치는 전국 값보다 {signed(num("stage2.stereotype.ever.terra_C2.bias_pp"))}, {signed(num("stage2.stereotype.weekly.terra_C2.bias_pp"))}, {signed(num("stage2.stereotype.carb.terra_C2.bias_pp"))}%⁠포인트 치우쳤습니다. 패널 절대값 없이 쓸 수 있는 자료와, 패널을 어디까지 믿을지의 기록이 함께 필요합니다.
              </dd>
            </dl>
            <p className="small">세 항목은 제로 음료 경험, 제로 음료 주 1회 이상, 탄산 1순위입니다. 패널은 gpt-6.1-terra의 페르소나 조건 C2이고, 패널 값은 시험 truth 전체의 실제 값에 치우침을 더한 값입니다. 시험 truth의 일부는 패널 본인입니다.</p>
            <Caveats items={caveats(["stage2.stereotype.weekly.terra_C2.bias_pp"])} />
          </Evidence>
        </div>
      </Scene>

      <Scene tone="glass" id="flow">
        <h2>패널은 훑고, 네 곳은 사람이 정합니다</h2>
        <p className="say">시스템은 설문을 보내지 않습니다. 점선은 아직 설계이고, 실제 조사를 만난 적이 없습니다.</p>
        <FlowLine />
        <p className="small figure-note">
          시연 승인은 사람이 하지 않았고, 작은 실행 한 번만 응모자가 터미널에서 승인했으며, 입력한 사람이 누구인지 코드는 확인하지 못합니다. <Link href="/run#human-run">승인 기록</Link>
        </p>
        <Evidence summary="흐름을 표로 보기">
          <FlowTable />
        </Evidence>
      </Scene>

      <Scene id="receive">
        <h2 className="h-long">담당자는 패널 절대값 대신 제안과 반대 이유를 받습니다</h2>
        <p className="say">
          <strong>시연 전용, 정답 없음:</strong> 카드는 모두 가상이고, 이 시연은 후보를 하나도 줄이지 못했습니다. 세 안 유지는 패널의 판단이 아니라 시연 값을 본 뒤 쓴 5%⁠포인트 기준의 결과입니다.
        </p>
        <div className="shelf">
          {bubbles.map(({ card, kind, line }) => {
            const summary = cardSummary(card);
            return (
              <figure className="shelf-item" key={card}>
                <blockquote className="bubble">
                  {line}
                  <span className="bubble-mark">LLM 문장, 응답자의 말이 아님</span>
                </blockquote>
                <div className="shelf-rail">
                  <Vessel letter={card} kind={kind} stamp={str(`stage4.demo8.action.${card}`)} />
                </div>
                <figcaption className="shelf-cap">
                  <strong>안 {card}, 가상 카드</strong>
                  {summary.attributes}. {summary.price}
                </figcaption>
              </figure>
            );
          })}
          <figure className="shelf-item shelf-control">
            <div className="shelf-gap">
              <strong>
                {gapLow}~{gapHigh}%⁠포인트 낮음
              </strong>
              대조 카드가 세 후보보다 낮게 나온 폭입니다. 패널 내부 값의 차이이고, 패널 값은 시장 수치가 아닙니다.
            </div>
            <div className="shelf-rail">
              <Vessel letter="N" dim />
            </div>
            <figcaption className="shelf-cap">
              <strong>일부러 어설프게 만든 대조 카드</strong>
              {cardSummary("N").attributes}. {cardSummary("N").price}. 한 장으로 본 약한 점검입니다.
            </figcaption>
          </figure>
        </div>
        <p className="small shelf-note">패널은 탈락을 확정하지 못하고, 실측 대상은 담당자가 고릅니다. 선반 높이는 그림이고 비율이 아닙니다.</p>
        <Evidence summary="안별 제안표, 방향 메모, 반대 이유 전체 보기">
          <Glossary />
          <p className="small">
            보고서 본문에는 패널 절대값이 없습니다. 아래 제안표와 방향 메모처럼 패널 내부 차이는 보고서에 그대로 있습니다. 세 후보를 같은 선반에 둔 것은 안 사이 차이가 고를 근거가 아니기 때문입니다.
          </p>
          <h3>시연 결과: 안별 제안</h3>
          <p className="small">
            <strong>시연 전용, 정답 없음, 카드 3장은 가상.</strong> 아래 제안은 어느 안이 낫다는 뜻이 아닙니다. Terra, Luna는 패널을 돌린 두 모델이고 %⁠포인트 값은 패널 내부 값입니다. 통과하지 못한 규칙은 <Link href="/results#failures">측정 결과 첫 표</Link>에 있습니다.
          </p>
          <ActionTable />
          <Caveats items={caveats(["stage4.demo8.action.A", "stage4.human2.action.A", "stage4.pair_accuracy.1_to_3pp.pairs"])} />
          <p id="human-approved">
            <strong>사람이 승인한 작은 실행 한 번:</strong> 위 표는 사람이 승인하지 않은 시연입니다. 따로 {num("stage4.human2.plan.n_personas")}명, 카드 {any<string[]>("stage4.human2.plan.cards").length}장, 두 모델의 실행 한 번(human2)을 사람이 터미널에서 이름과 계획 해시를 입력해 승인했고, 세 안 모두 {str("stage4.human2.action.A")}로 시연과 같은 결론이 나왔습니다. 코드는 입력한 사람이 누구인지 확인하지 못하고, 정답이 없어 이 실행으로도 안을 고를 수 없습니다. <Link href="/run#human-run">기록 보기</Link>
          </p>
          <h3>안 사이의 방향</h3>
          <OrderNotes />
          <h3 id="explore-sample">탐색 출력 표본: 반대 이유</h3>
          <p>
            {stage4.explore.marking} 안마다 끌리는 점, 세그먼트 가설, 설문 문항 초안도 냅니다. <Link href="/run#explore">전체 표본 보기</Link>
          </p>
          <div className="card-grid">
            <ExploreCard card="A" only="objections" />
            <ExploreCard card="B" only="objections" />
            <ExploreCard card="C" only="objections" />
          </div>
        </Evidence>
      </Scene>

      <Scene tone="glass" id="ladder">
        <h2>보정해도 단순 통계와 구별되지 않습니다</h2>
        <p className="say">응답자 본인의 실제 답을 넣은 패널도 단순 통계를 이기는지 보는 규칙을 넘지 못해, 이 결과를 LLM 실패의 증거로 읽지 않습니다.</p>
        <ErrorLadder steps={ladder} gapText={ladderGap} axis="12칸(연령대와 성별) 평균 오차, %⁠포인트. 짧을수록 실제에 가깝습니다." />
        <p className="ladder-read">
          패널 보정이 실제 200명 평균보다 짧아 보여도, 이 차이 {fixed(Math.abs(num(`stage2.n200.row.terra_C2.E4.average.minus_E2.mean_diff`)))}은 사전 등록 잡음 기준 {fixed(num("stage2.noise_floor.average"))}보다 작아 패널 이득으로 읽지 않습니다.
        </p>
        <p className="small">세 음료 항목의 평균이고 패널 값은 시장 수치가 아닙니다. 새 콘셉트의 정확도와 판매량은 재지 않았습니다.</p>
        <Evidence summary="비교 상대와 구간, 앞선 측정 요약 보기">
          <Glossary />
          <h3>실제 200명에 패널을 더해도 같은 200명의 나이·성별 회귀와 구별되지 않습니다</h3>
          <p>
            E4 - R1은 {signed(num(`${e4r}.mean_diff`))}pp {ciText(interval(`${e4r}.ci95`))}(row), {signed(num(`${e4c}.mean_diff`))}pp {ciText(interval(`${e4c}.ci95`))}(cluster)입니다. 사전 고정한 비교 상대인 E2보다는 평균 {fixed(Math.abs(num("stage2.n200.row.terra_C2.E4.average.minus_E2.mean_diff")))}pp 낮지만 E2는 약한 상대이고, 그 차이도 사전 등록한 noise floor {fixed(num("stage2.noise_floor.average"))}pp보다 작습니다. R1을 row와 cluster 모두에서 이긴 조합은 0개입니다. 다만 응답자 본인의 실제 답을 넣은 패널도 규칙 v2에서 통과하지 못해, 이 결과를 LLM 실패의 증거로 읽을 수 없습니다. <Link href="/results#forest">측정 결과</Link>
          </p>
          <div className="table-wrap" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>사다리</th>
                  <th>코드</th>
                  <th className="num">12칸 평균 오차 pp</th>
                </tr>
              </thead>
              <tbody>
                {ladder.map((s) => (
                  <tr key={s.id}>
                    <td>{s.label}</td>
                    <td>{s.id === "E3" || s.id === "E4" ? `Terra C2 ${s.id}, row` : `${s.id}, row`}</td>
                    <td className="num">{s.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3>패널 원수치는 크게 치우칩니다</h3>
          <p>
            전국 값보다 Terra C2에서 {signed(num("stage2.stereotype.ever.terra_C2.bias_pp"))}, {signed(num("stage2.stereotype.weekly.terra_C2.bias_pp"))}, {signed(num("stage2.stereotype.carb.terra_C2.bias_pp"))}pp 치우칩니다. 그래서 시장 수치로 쓰지 않습니다. 패널의 ever 성별 차이는 {signed(num("stage2.stereotype.ever.terra_C2.gender_gap_pp"))}pp, 실제는 {signed(num("stage2.stereotype.ever.real_gender_gap_pp"))}pp입니다.
          </p>
          <h3>기존 음료 순서는 실제 200명과 2024 집계보다 덜 맞습니다</h3>
          <p>
            Spearman은 Terra C2 {fixed(num(`${rank}.panel_C2.spearman.value`), 3)}, 실제 200명(row) {fixed(num(`${rank}.direct_row.spearman.value`), 3)}, 2024 원자료 집계 {fixed(num(`${rank}.krei_2024.spearman.value`), 3)}입니다. 실제 차이 5pp 이상 쌍에서 패널 정확도는 {fixed(num("ranking.bands.panel_C2.true_gap.5pp_and_over.accuracy"), 3)}이고, 200명은 {fixed(num("ranking.bands.direct_row.true_gap.5pp_and_over.accuracy"), 3)}, 2024 집계는 {fixed(num("ranking.bands.krei_2024.true_gap.5pp_and_over.accuracy"), 3)}입니다.
          </p>
          <h3>에이전트 방어는 뚫렸고, 고친 뒤에도 일부가 통과합니다</h3>
          <p>
            실제 API 공격 {num("attacks.wf7.live_runs")}회에서 무승인 패널 실행과 예산 초과는 없었습니다(시도 대부분 1회). 그러나 사실형 유도 문장은 3회 모두 접수를 통과했고, 30명 Luna 탐침에서 패널 내부 값을 {signed(num("attacks.wf7.probe.kept_minus_clean_t2b_pp"), 1)}pp {ciText(interval("attacks.wf7.probe.ci95"), 1, false)} 올렸습니다. 고친 뒤 뚫렸던 {num("attacks.replay.live.total")}회를 다시 돌렸더니 이번에는 모두 통과하지 못했지만, 패턴에 걸리지 않는 유도 문장 {num("attacks.replay.offline.leading_variants_total") - num("attacks.replay.offline.leading_variants_flagged")}개({num("attacks.replay.offline.leading_variants_total")}개 중) 등 아직 통과하는 것이 남아 있습니다. <Link href="/attacks">공격 기록</Link>
          </p>
          <Caveats items={caveats(cite)} />
        </Evidence>
      </Scene>

      <Scene tone="mist" id="detectable">
        <h2>실제 200명은 작은 차이를 못 가립니다</h2>
        <p className="say">가려낼 수 있는 선 아래의 차이는 원가와 라인 구성 같은 다른 근거로 고르거나 표본을 늘립니다.</p>
        <SampleSlider params={{ z_alpha: d.z_alpha, z_power: d.z_power, p: d.p }} marks={marks} />
        <Evidence summary="필요 인원 표와 한 사람이 두 안을 볼 때 보기">
          <p>
            200명을 두 안에 {num("stage4.detectable.n_arm")}명씩 나누면 실제 차이가 {num("stage4.detectable.between_mde_pp")}pp보다 작을 때 가려내기 어렵습니다. 한 사람이 두 안을 모두 보면 두 안 응답의 상관에 따라 {num("stage4.detectable.within_mde_pp.rho_0.0")}pp(상관 0), {num("stage4.detectable.within_mde_pp.rho_0.3")}pp(0.3), {num("stage4.detectable.within_mde_pp.rho_0.5")}pp(0.5)입니다. 실제 사람의 상관은 재지 않았습니다.
          </p>
          <DetectableTable />
          <p className="small">산식: {d.arithmetic}. 슬라이더는 같은 산식을 브라우저에서 계산하고, scripts/check_detectable.mjs가 results/stage4/detectable.json과 대조합니다.</p>
          <Caveats items={caveats(["stage4.detectable.between_mde_pp"])} />
        </Evidence>
      </Scene>

      <Scene tone="glass" id="why">
        <h2>그래도 돌리는 이유는 재료와 기록입니다</h2>
        <p className="say">설문 전에 반대 이유와 문항 초안을 얻고, 어설픈 안을 훑을 재료를 얻고, 패널을 실제 응답과 겨룬 기록을 남깁니다. 앞의 두 쓸모는 아직 재지 않았습니다.</p>
        <div className="cost">
          <div>
            <Figure label={`패널 감사 한 번의 측정 비용. 호출 비용 ${usd(num("spend.gate"), 2)}, 실행 시간 합계 ${totalSeconds.toFixed(1)}초로 10분 미만, Terra ${gate.seconds.terra_from_call_log}초와 Luna ${gate.seconds.luna}초. 300명, 두 모델.`}>
              <div className="cost-big">
                <div>
                  USD {fixed(num("spend.gate"))}
                  <small>호출 비용, 잰 값</small>
                </div>
                <div>
                  10분 미만
                  <small>300명, 모델 2개 한 번, {totalSeconds.toFixed(1)}초를 잰 값</small>
                </div>
              </div>
              <div className="time-bar">
                <div style={{ flex: gate.seconds.terra_from_call_log }}>Terra {gate.seconds.terra_from_call_log}초</div>
                <div style={{ flex: gate.seconds.luna }}>Luna {gate.seconds.luna}초</div>
              </div>
            </Figure>
            <p className="small figure-note">Terra와 Luna는 패널을 돌린 두 모델입니다. 자료 준비와 사람 시간은 빠져 있고, 실측 조사 비용과 비교하지 않았습니다.</p>
          </div>
          <div className="camp">
            <svg viewBox="0 0 72 96" aria-hidden="true" className="camp-glass">
              <ellipse cx={36} cy={8} rx={30} ry={5} fill="none" stroke="#12323B" strokeWidth={2.5} strokeDasharray="5 5" />
              <path d="M6 8 L12 88 Q12.5 92 16 92 L56 92 Q59.5 92 60 88 L66 8" fill="none" stroke="#12323B" strokeWidth={2.5} strokeDasharray="5 5" />
              <text x={36} y={62} textAnchor="middle" className="camp-mark">
                ?
              </text>
            </svg>
            <div>
              <strong>본선 가설, 재지 않음</strong>
              지금 성적은 공개 자료로 만든 페르소나의 것입니다. 롯데칠성음료의 조사 자료와 구매 이력을 붙이면 같은 시험을 넘을 수 있다는 가설이고, 합격선은 답을 보기 전에 고정합니다.
            </div>
          </div>
        </div>
        <Evidence summary="감사 비용과 이번 측정의 전체 설명 보기">
          <Glossary />
          <p>
            패널을 실제 응답과 대조하는 감사는 호출 비용이 적게 들었습니다. 관문 1회에 Terra와 Luna 각 {gate.calls_answered.terra}건, {usd(num("spend.gate"))}, 실행 시간 Terra {gate.seconds.terra_from_call_log}초와 Luna {gate.seconds.luna}초였습니다. 이 한 번으로 12칸 평균 오차가 Terra C2 {num("gate.terra.C2.average_cell_mae")}pp, Luna C1 {num("gate.luna.C1.average_cell_mae")}pp로, 모든 칸에 전국 평균 하나를 넣은 {num("gate.terra.C2.average_constant_cell_mae")}pp보다 크다는 것이 나왔습니다. 호출 비용과 실행 시간만 잰 값이고, 자료 준비와 사람 시간은 빠져 있으며 실측 조사 비용과 비교하지 않았습니다.
          </p>
          <p>
            시연의 음성 대조 카드는 세 후보보다 패널 내부 값이 {gapLow}~{gapHigh}pp 낮았습니다. 대조 카드 한 장의 약한 점검입니다.
          </p>
          <p>
            같은 시험은 같은 200명의 회귀(R1)와의 비교, 그리고 조사 단위를 온전히 둔 건강검진입니다. 본선 현장 자료에 그런 자료가 있으면 합격선을 답을 보기 전에 고정하고 잽니다. 이 사이트에는 롯데 자료가 없습니다.
          </p>
          <p className="small">
            Terra 실행 시간은 호출 로그에서 잰 값이고 수치 시트에 없습니다. results/gate_run_summary.json의 {gate.terra_wall_clock_in_summary_with_failed_attempts}초는 충전 전 실패 기록까지 합친 값입니다.
          </p>
          <Caveats items={caveats(["spend.gate", "gate.terra.C2.average_cell_mae", "stage4.detectable.between_mde_pp", "stage2.stereotype.ever.terra_C2.bias_pp", "demo.terra.negative.A.mean", "stage4.policy.default"])} />
        </Evidence>
      </Scene>

      <Scene tone="deep" id="health-check">
        <h2>패널 절대값은 보고서에 넣지 않습니다</h2>
        <p className="say">실제 200명과의 대결은 건강검진으로만 기록합니다. 건강검진은 실제 설문을 만난 적이 없고, 이 결정은 결과를 본 뒤에 정한 사후 결정입니다.</p>
        <ReportGate keeps={health.consecutive_keeps} />
        <Evidence summary="결정 내용, 근거, 경로 상태 보기">
          <Glossary />
          <HealthCheckDecision />
          <h3>이렇게 정한 근거 (사후 계산)</h3>
          <HealthCheckReasons />
          <h3>경로가 어디까지 와 있는가</h3>
          <DuelStatusTable />
          <Caveats items={caveats(["stage4.demo8.ingest.report_status", "stage4.duel.acceptance.label", "stage4.posthoc.row.terra_C1.keep_rate"])} />
        </Evidence>
      </Scene>

      <Scene id="checked">
        <h2>검증한 것과 검증하지 못한 것</h2>
        <div className="pair">
          <div>
            <h3>검증한 것</h3>
            <ul>
              <li><span>패널이 기존 음료 행동 3개 항목의 12칸을 얼마나 맞히는지 측정</span></li>
              <li><span>패널 보정과 단순 통계의 비교: 구별되지 않음</span></li>
              <li><span>음료 15개 순서: 패널이 실제 200명과 지난해 집계보다 낮음</span></li>
              <li><span>응답자, 가구, 조사 단위의 분할과 누출</span></li>
              <li><span>계획을 먼저 고정한 순서, 로그로 확인</span></li>
              <li><span>에이전트의 거절, 도구 순서, 예산, 시험한 형태 안에서</span></li>
              <li><span>탐색 문장 필터, 시험한 형태 안에서</span></li>
            </ul>
          </div>
          <div className="pair-no">
            <h3>검증하지 못한 것</h3>
            <ul>
              <li><span>새 콘셉트 반응의 정확도와 판매량, 신제품 성패</span></li>
              <li><span>탈락 제안의 효용과 탐색 가설의 쓸모</span></li>
              <li><span>내부 콘셉트 테스트 대비 정확도</span></li>
              <li><span>독립 표본 검증과 모집단 불확실성</span></li>
              <li><span>실제 설문과 만난 건강검진</span></li>
              <li><span>사람 승인 화면: 터미널 명령 한 번뿐이고, 입력한 사람은 코드가 확인하지 못함</span></li>
              <li><span>공격으로 찾은 구멍을 모두 막았는지: <Link href="/attacks">아직 통과하는 것이 있음</Link></span></li>
            </ul>
          </div>
        </div>
        <Evidence summary="범위와 한계 전체 표, 효과를 보지 못한 시도 보기">
          <Glossary />
          <div className="table-wrap">
            <table className="stack">
              <thead>
                <tr>
                  <th style={{ width: "32%" }}>대상</th>
                  <th style={{ width: "16%" }}>상태</th>
                  <th>범위와 한계</th>
                </tr>
              </thead>
              <tbody>
                <tr className="group-row">
                  <td colSpan={3}>검증한 것</td>
                </tr>
                {verified.map(renderRow)}
                <tr className="group-row">
                  <td colSpan={3}>검증하지 못한 것</td>
                </tr>
                {notVerified.map(renderRow)}
              </tbody>
            </table>
          </div>
          <h3 id="tried">시도했지만 효과를 보지 못한 것</h3>
          <p>저장된 답으로 계산했고 이 측정들의 새 페르소나 호출은 {num("spend.stage4.panel_calls")}건입니다. 기존 음료 행동에서 잰 값입니다.</p>
          <div className="table-wrap">
            <table className="stack">
              <thead>
                <tr>
                  <th style={{ width: "32%" }}>질문</th>
                  <th style={{ width: "16%" }}>결과</th>
                  <th>내용</th>
                </tr>
              </thead>
              <tbody>{tried.map(renderRow)}</tbody>
            </table>
          </div>
          <p className="small">
            <Link href="/results#tried">측정 결과의 해 봤지만 효과가 없던 것</Link>
          </p>
        </Evidence>
      </Scene>
    </>
  );
}
