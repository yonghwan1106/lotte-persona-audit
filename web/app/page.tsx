import Link from "next/link";
import { Caveats } from "@/components/Notes";
import { ActionTable, DetectableTable, DuelStatusTable, ExploreCard, OrderNotes, seedRunsFailed, SEED_RUNS } from "@/components/Stage4";
import stage4 from "@/data/stage4.json";
import { bool, caveats, ciText, fixed, interval, num, signed } from "@/lib/numbers";

type Row = { what: string; state: string; ok: boolean; scope: React.ReactNode };

export default function HomePage() {
  const e4r = "stage2.n200.row.terra_C2.E4.average.minus_R1";
  const e4c = "stage2.n200.cluster.terra_C2.E4.average.minus_R1";
  const rank = "ranking.merged_coffee_15";
  const alloc = "stage4.allocation.R1.panel_excluded.cell_mae";

  const verified: Row[] = [
    {
      what: "기존 음료 행동 3개 항목의 12칸 재현",
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
      scope: `시나리오 ${num("scenarios.fix_stage.passed")}/${num("scenarios.fix_stage.runs")}회 통과(조합당 3회). 거절률 추정치가 아닙니다. 실제 API 공격에서 뚫린 것과 아직 통과하는 것은 공격 기록에 있습니다.`,
    },
  ];
  const notVerified: Row[] = [
    { what: "새 콘셉트 반응의 정확도, 신제품 성패", state: "재지 않음", ok: false, scope: "기존 행동을 잘 맞혀도 새 콘셉트를 맞힌다는 뜻은 아닙니다. 시연의 구매 의향 값은 패널 내부 값이고 정답이 없습니다." },
    { what: "탈락 제안의 효용", state: "재지 않음", ok: false, scope: "공개 자료로 증명할 수 없습니다. 첫 시범의 되살림 검증으로 재야 합니다. 탈락 제안 기준 5pp는 기존 음료에서 나온 사후 가설입니다." },
    { what: "탐색 가설의 쓸모", state: "재지 않음", ok: false, scope: "LLM 출력이고 응답자의 말이 아닙니다. 실제 소비자에게 확인하지 않았습니다." },
    { what: "내부 콘셉트 테스트 대비 정확도", state: "재지 않음", ok: false, scope: "롯데칠성음료 내부 자료를 쓰지 않았습니다." },
    { what: "독립 표본 검증", state: "못 함", ok: false, scope: `시험 truth의 psfwt ${fixed(num("stage2.panel_share_of_test_psfwt"))}%가 패널 본인입니다. 패널 밖 truth로 다시 본 값은 측정 결과에 따로 있습니다.` },
    { what: "모집단 불확실성", state: "못 함", ok: false, scope: "2단계 구간은 보정 풀과 시험 패널을 고정한 채 추출만 반복한 값입니다." },
    { what: "사람 승인 화면", state: "없음", ok: false, scope: "시연 승인은 CLI 인자이고 사람이 하지 않았습니다. 사람이 터미널에서 입력하는 명령은 만들었지만 실행한 적이 없고, 입력한 이름이 누구인지 코드는 확인하지 못합니다." },
    { what: "조사 단위 군집 효과의 원인", state: "확인 못 함", ok: false, scope: "주 1회 항목은 정답 자체가 조사 단위 효과를 담을 수 있어 모델이 틀린 것과 조사가 흔들린 것을 완전히 가르지 못합니다." },
  ];

  const renderRow = (row: Row) => (
    <tr key={row.what}>
      <td>{row.what}</td>
      <td data-label="상태">
        <span className={row.ok ? "status" : "status no"}>{row.state}</span>
      </td>
      <td>{row.scope}</td>
    </tr>
  );

  const signals = ["terra_minus_luna", "c1_minus_c2", "repeat_sd"];
  const cite = [`stage2.stereotype.ever.terra_C2.bias_pp`, `${e4r}.mean_diff`, `${rank}.panel_C2.spearman.value`, "scenarios.fix_stage.passed", "attacks.wf7.probe.kept_minus_clean_t2b_pp", "attacks.replay.live.total"];
  const measured: Row[] = [
    {
      what: "패널로 실제 200명을 더 잘 나눌 수 있는가",
      state: "도움 없음",
      ok: false,
      scope: `패널 배분 - 비례 배분: 칸 오차 ${signed(num(`${alloc}.panel_neyman_minus_proportional.average.mean_diff`), 3)}pp ${ciText(interval(`${alloc}.panel_neyman_minus_proportional.average.ci95`), 3)}. 사전 기준 ${bool("stage4.allocation.reading.panel_helps_over_proportional") ? "통과" : "미달"}. 패널로 나눌 근거가 없습니다.`,
    },
    {
      what: "실측 전에 틀린 칸을 집어내는가",
      state: "지목 못 함",
      ok: false,
      scope: `신호 ${signals.length}개 중 사전 기준을 넘은 것 ${signals.filter((s) => bool(`stage4.flags.${s}.names_wrong_cells`)).length}개. 패널 신호로 실측 전에 틀린 칸을 고를 수 없습니다.`,
    },
    {
      what: "실측 뒤 패널 값을 남길지 정하는 규칙",
      state: "기준 근처",
      ok: false,
      scope: `답을 넣은 대조와 대체 패널을 동결 시드에서 갈랐고(유지율 ${num("stage4.duel.acceptance.positive_keep_rate")}, ${num("stage4.duel.acceptance.surrogate_terra_slot.keep_rate")}), 다른 시드 ${SEED_RUNS.length}개 중 ${seedRunsFailed()}개에서 기준을 넘지 못했습니다. 패널을 검증하는 도구로 쓰지 않습니다.`,
    },
  ];

  return (
    <>
      <h1>콘셉트를 실측 설문에 넘기기 전에, 어떤 안을 넣을지 판단 자료를 냅니다</h1>
      <p className="lead">
        콘셉트 카드를 넣으면 합성 패널(LLM 페르소나)이 먼저 읽습니다. 담당자는 안별 제안, 반대 이유와 문항 초안, 실제 200명 설문 계획을 받습니다. 패널은 탈락을 확정하지 못하고, 설문에 넣을 안은 담당자가 고릅니다. 신제품 성패를 예측하지 않습니다.
      </p>

      <h2 className="first-h2">시연 결과: 안별 제안</h2>
      <p className="small">
        <strong>시연 전용, 정답 없음, 카드 3장은 가상.</strong> 아래 제안은 어느 안이 낫다는 뜻이 아닙니다. terra, luna는 패널을 돌린 두 모델이고 pp 값은 패널 내부 값입니다. 통과하지 못한 규칙은 <Link href="/results#failures">측정 결과 첫 표</Link>에 있습니다.
      </p>
      <ActionTable />
      <Caveats items={caveats(["stage4.demo7.action.A"])} />

      <h3>안 사이의 방향</h3>
      <OrderNotes />

      <h2 id="detectable">200명 설문으로 가려낼 수 있는 차이</h2>
      <p>
        200명을 두 안에 {num("stage4.detectable.n_arm")}명씩 나누면 실제 차이가 {num("stage4.detectable.between_mde_pp")}pp보다 작을 때 가려내기 어렵습니다. 한 사람이 두 안을 모두 보면 두 안 응답의 상관에 따라 {num("stage4.detectable.within_mde_pp.rho_0.0")}pp(상관 0), {num("stage4.detectable.within_mde_pp.rho_0.3")}pp(0.3), {num("stage4.detectable.within_mde_pp.rho_0.5")}pp(0.5)입니다. 실제 사람의 상관은 재지 않았습니다. 이보다 작은 차이는 원가와 라인 구성 같은 다른 근거로 고르거나, 아래 인원으로 표본을 늘립니다.
      </p>
      <DetectableTable />
      <Caveats items={caveats(["stage4.detectable.between_mde_pp"])} />

      <h2 id="explore-sample">탐색 출력 표본: 반대 이유</h2>
      <p>{stage4.explore.marking} 안마다 끌리는 점, 세그먼트 가설, 설문 문항 초안도 냅니다. <Link href="/run#explore">전체 표본 보기</Link></p>
      <div className="card-grid">
        <ExploreCard card="A" only="objections" />
        <ExploreCard card="B" only="objections" />
        <ExploreCard card="C" only="objections" />
      </div>

      <h2 id="duel-status">실측 뒤 대결: 어디까지 와 있는가</h2>
      <p>실제 200명을 받으면 패널 값을 남길지 뺄지 규칙으로 정하려는 경로입니다. 경로는 있지만 실제 콘셉트 설문으로 돌린 적이 없습니다.</p>
      <DuelStatusTable />
      <Caveats items={caveats(["stage4.ingest.decision"])} />

      <h2>4단계에서 잰 것</h2>
      <p>저장된 답으로 계산했고 새 페르소나 호출은 {num("spend.stage4.panel_calls")}건입니다. 기존 음료 행동에서 잰 값입니다.</p>
      <div className="table-wrap">
        <table className="stack">
          <thead>
            <tr>
              <th style={{ width: "32%" }}>질문</th>
              <th style={{ width: "16%" }}>결과</th>
              <th>내용</th>
            </tr>
          </thead>
          <tbody>{measured.map(renderRow)}</tbody>
        </table>
      </div>
      <p className="small">
        <Link href="/results#allocation">측정 결과 7, 8, 9절</Link>
      </p>

      <h2>무엇을 검증했고 무엇을 검증하지 못했는가</h2>
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

      <h2>기존 음료 측정의 핵심 결과 네 가지</h2>
      <ol className="results-list">
        <li>
          <h3>1. 패널 원수치는 크게 치우칩니다</h3>
          <p>
            전국 값보다 Terra C2에서 {signed(num("stage2.stereotype.ever.terra_C2.bias_pp"))}, {signed(num("stage2.stereotype.weekly.terra_C2.bias_pp"))}, {signed(num("stage2.stereotype.carb.terra_C2.bias_pp"))}pp 치우칩니다. 그래서 시장 수치로 쓰지 않습니다. 패널의 ever 성별 차이는 {signed(num("stage2.stereotype.ever.terra_C2.gender_gap_pp"))}pp, 실제는 {signed(num("stage2.stereotype.ever.real_gender_gap_pp"))}pp입니다.
          </p>
          <p className="small">
            <Link href="/results">측정 결과 1, 4절</Link>
          </p>
        </li>
        <li>
          <h3>2. 실제 200명에 패널을 더해도 같은 200명의 나이·성별 회귀와 구별되지 않습니다</h3>
          <p>
            E4 - R1은 {signed(num(`${e4r}.mean_diff`))}pp {ciText(interval(`${e4r}.ci95`))}(row)입니다. 사전 고정한 비교 상대인 E2보다는 평균 {fixed(Math.abs(num("stage2.n200.row.terra_C2.E4.average.minus_E2.mean_diff")))}pp 낮지만 E2는 약한 상대이고, 그 차이도 사전 등록한 noise floor {fixed(num("stage2.noise_floor.average"))}pp보다 작습니다. R1을 row와 cluster 모두에서 이긴 조합은 0개입니다. 다만 응답자 본인의 실제 답을 넣은 패널도 규칙 v2에서 통과하지 못해, 이 결과를 LLM 실패의 증거로 읽을 수 없습니다.
          </p>
          <p className="small">
            <Link href="/results">측정 결과 2, 5절</Link>
          </p>
        </li>
        <li>
          <h3>3. 기존 음료 순서는 실제 200명과 2024 집계보다 덜 맞습니다</h3>
          <p>
            Spearman은 Terra C2 {fixed(num(`${rank}.panel_C2.spearman.value`), 3)}, 실제 200명(row) {fixed(num(`${rank}.direct_row.spearman.value`), 3)}, 2024 원자료 집계 {fixed(num(`${rank}.krei_2024.spearman.value`), 3)}입니다. 실제 차이 5pp 이상 쌍에서 패널 정확도는 {fixed(num("ranking.bands.panel_C2.true_gap.5pp_and_over.accuracy"), 3)}이고, 200명은 {fixed(num("ranking.bands.direct_row.true_gap.5pp_and_over.accuracy"), 3)}, 2024 집계는 {fixed(num("ranking.bands.krei_2024.true_gap.5pp_and_over.accuracy"), 3)}입니다.
          </p>
          <p className="small">
            <Link href="/results">측정 결과 3절</Link>
          </p>
        </li>
        <li>
          <h3>4. 에이전트 방어는 뚫렸고, 고친 뒤에도 일부가 통과합니다</h3>
          <p>
            실제 API 공격 {num("attacks.wf7.live_runs")}회에서 무승인 패널 실행과 예산 초과는 없었습니다(시도 대부분 1회). 그러나 사실형 유도 문장은 3회 모두 접수를 통과했고, 30명 Luna 탐침에서 패널 내부 값을 {signed(num("attacks.wf7.probe.kept_minus_clean_t2b_pp"), 1)}pp {ciText(interval("attacks.wf7.probe.ci95"), 1, false)} 올렸습니다. 고친 뒤 뚫렸던 {num("attacks.replay.live.total")}회를 다시 돌렸더니 이번에는 모두 통과하지 못했지만, 패턴에 걸리지 않는 유도 문장 {num("attacks.replay.offline.leading_variants_total") - num("attacks.replay.offline.leading_variants_flagged")}개({num("attacks.replay.offline.leading_variants_total")}개 중) 등 아직 통과하는 것이 남아 있습니다.
          </p>
          <p className="small">
            <Link href="/attacks">공격 기록</Link>
          </p>
        </li>
      </ol>

      <Caveats items={caveats(cite)} />
    </>
  );
}
