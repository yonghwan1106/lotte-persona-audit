import type { Metadata } from "next";
import { Caveats, SourceLine } from "@/components/Notes";
import { ReplaySteps, type Step } from "@/components/ReplaySteps";
import { ActionTable, DetectableTable, DuelStatusTable, EXPLORE_SECTIONS, ExploreCard, HealthCheckDecision, HumanActionTable, OrderNotes } from "@/components/Stage4";
import demo from "@/data/demo.json";
import stage4 from "@/data/stage4.json";
import { any, bool, caveats, ciText, fixed, num, interval, signed, sources, str, usd } from "@/lib/numbers";

export const metadata: Metadata = { title: "실행 기록 · 합성 패널 감사 기록" };

const ROLE: Record<string, string> = { candidate: "후보", paraphrase: "바꿔 쓴 카드", brand: "브랜드 표시 카드", negative_control: "음성 대조" };
const MODEL: Record<string, string> = { "gpt-6.1-terra": "Terra", "gpt-6-luna": "Luna" };
const SEGMENT: Record<string, string> = { all: "전체", "19-39_f": "19~39 여성", "19-39_m": "19~39 남성", "40-59_f": "40~59 여성", "40-59_m": "40~59 남성", "60+_f": "60+ 여성", "60+_m": "60+ 남성" };

type VerdictRow = (typeof demo.verdict.rows)[number];

function VerdictTable({ rows }: { rows: VerdictRow[] }) {
  return (
    <div className="table-wrap" tabIndex={0}>
      <table>
        <thead>
          <tr>
            <th>카드</th>
            <th>모델</th>
            <th>세그먼트</th>
            <th className="num">n</th>
            <th>실행 상태</th>
            <th>판정</th>
            <th>보고서 본문의 절대값</th>
            <th>순서 사용</th>
            <th>표시</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.card}${r.model}${r.segment}`}>
              <td>{r.card}</td>
              <td>{MODEL[r.model] ?? r.model}</td>
              <td>{SEGMENT[r.segment] ?? r.segment}</td>
              <td className="num">{r.n}</td>
              <td>{r.run_status}</td>
              <td>{r.label}</td>
              <td>{r.absolute_shown ? "표시" : "숨김"}</td>
              <td>{r.order_allowed ? "허용" : "불가"}</td>
              <td>{r.flags.join(", ") || "없음"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function RunPage() {
  const overall = demo.verdict.rows.filter((r) => r.segment === "all");
  const hypotheses = (demo.steps.find((s) => s.event === "narrator_output")?.detail as { sentences: string[] }).sentences;
  const a = demo.allocation;
  const demoKeys = ["demo.terra.noise_upper", "demo.terra.A.label", "demo.allocation.overall.n"];
  const pairs = ["A_minus_B", "A_minus_C", "B_minus_C"];
  const models = ["terra", "luna"] as const;
  const exploreCards = ["A", "B", "C"] as const;
  const human = stage4.human_run;

  return (
    <>
      <h1>실행 기록</h1>
      <div className="band">
        <p>
          <strong>시연 전용, 정답 없음.</strong> 카드 6장은 모두 가상입니다. 구매 의향은 패널 내부 값이고 시장 수치나 판매 전망이 아닙니다. 이 페이지가 재생하는 시연의 승인은 사람이 하지 않았습니다. 사람이 승인한 작은 실행 한 번은 <a href="#human-run">별도 절</a>에 있습니다. 어느 실행으로도 안을 고를 수 없습니다.
        </p>
      </div>
      <p className="lead">
        감사 에이전트가 카드를 받아 계획, 패널, 진단, 판정, 탐색, 실측 200명 배분, 문항지, 원장까지 진행한 기록입니다. 페르소나 문장과 패널 이유 원문은 싣지 않습니다.
      </p>
      <p className="small">
        재생 대상은 4단계 실행 <code>{demo.run_id}</code>(results/stage4/{demo.run_id})입니다. 판정표와 문항지 파일은 앞 실행 results/agent/demo5와 바이트 단위로 같고, 배분표는 숫자가 같으며 카드별 용도 문장만 다릅니다. 탐색 호출도 앞 실행의 캐시를 읽어 이 실행에서는 0건입니다. 매니페스트 <code>{demo.manifest_sha256.slice(0, 16)}…</code>, 규칙 {demo.rule_version}. 이 재생의 패널 답은 앞 실행의 것이고, 이 실행까지 4단계의 새 패널 호출은 {num("spend.stage4.panel_calls")}건입니다.
      </p>

      <h2 id="action">안별 제안</h2>
      <p>패널은 탈락을 확정하지 못합니다. 아래는 제안이며 어느 안이 낫다는 뜻이 아닙니다. 실측 대상은 담당자가 고릅니다. 이유 문장은 코드가 씁니다.</p>
      <ActionTable />
      <h3>안 사이의 방향</h3>
      <OrderNotes />
      <Caveats items={caveats(["stage4.demo8.action.A", "stage4.pair_accuracy.1_to_3pp.pairs"])} />

      <h3>작은 차이를 가려내려면</h3>
      <p>
        200명을 두 안에 {num("stage4.detectable.n_arm")}명씩 나누면 실제 차이가 {num("stage4.detectable.between_mde_pp")}pp보다 작을 때 가려내기 어렵습니다. 한 사람이 두 안을 모두 보면 {num("stage4.detectable.within_mde_pp.rho_0.0")}pp(상관 0), {num("stage4.detectable.within_mde_pp.rho_0.3")}pp(0.3), {num("stage4.detectable.within_mde_pp.rho_0.5")}pp(0.5)이고, 순서 효과를 막으려 첫 카드만 보면 다시 {num("stage4.detectable.between_mde_pp")}pp입니다.
      </p>
      <DetectableTable />
      <p className="small">산식: {stage4.detectable.arithmetic}</p>
      <Caveats items={caveats(["stage4.detectable.between_mde_pp"])} />

      <h2 id="human-run">사람이 터미널에서 승인한 실행</h2>
      <div className="band">
        <p>
          <strong>작은 실행 한 번을 사람이 승인했습니다.</strong> run <code>{human.run_id}</code>, {human.approval.at.slice(0, 10)}, 터미널에 입력한 이름 {str("stage4.human2.approval.typed_name")}. 이름과 계획 해시를 입력하는 명령이고, <strong>코드는 입력한 사람이 누구인지 확인하지 못합니다.</strong> 위 시연을 포함한 앞선 시연 승인은 사람이 하지 않았습니다.
        </p>
        <p>
          첫 시도 <code>human1</code>은 이름을 입력한 뒤 패널 호출 전에 코드 버그로 멈췄습니다. 고친 뒤 다시 실행한 것이 이 기록이고, 첫 시도의 기록도 저장소에 있습니다(results/stage4/human1).
        </p>
      </div>
      <p>
        {human.n_personas}명, 카드 {human.cards.join(", ")}, 두 모델({human.models.map((m) => MODEL[m] ?? m).join(", ")})입니다. 계획은 답 {num("stage4.human2.plan.answers").toLocaleString("en-US")}건이고, {num("stage4.human2.calls.answers_from_cache")}건은 앞 실행의 캐시에 있던 답이며 새로 받은 답은 {num("stage4.human2.calls.new_answers")}건입니다. 이 실행의 비용은 {usd(num("spend.stage4.human2.run"))}(패널 {usd(num("spend.stage4.human2.panel"))}, 탐색 {usd(num("spend.stage4.human2.explore"))})이고, {num("stage4.human2.plan.answers").toLocaleString("en-US")}건을 모두 새로 부를 때의 비용이 아닙니다. 매니페스트 <code>{human.manifest_sha256}</code>.
      </p>
      <HumanActionTable />
      <ul className="small">
        {human.action.notes.map((line) => (
          <li key={line}>{line}</li>
        ))}
        <li>이 실행도 시연 카드이고 정답이 없어 시연과 같은 결론을 내도 안을 고를 수 없습니다. 실측 대결을 돌리지 않아 원장의 real_results와 human_decision은 비어 있습니다.</li>
      </ul>
      <Caveats items={caveats(["stage4.human2.action.A", "stage4.human2.calls.new_answers", "spend.stage4.human2.run"])} />
      <SourceLine files={sources(["stage4.human2.action.A", "stage4.human2.calls.new_answers", "spend.stage4.human2.run"])} keys="stage4.human2.*, spend.stage4.human2.*" />

      <h2>카드</h2>
      <div className="card-grid">
        {demo.cards.map((card) => (
          <div key={card.id}>
            <div>
              <span className="card-id">{card.id}</span>
              <span className="role">{ROLE[card.role] ?? card.role}</span>
            </div>
            {card.text ? <p className="small">{card.text}</p> : <p className="small">속성: {card.attributes.join(", ")}. 가격대: {card.price_band}. 문구 원문은 이 페이지에 싣지 않습니다.</p>}
            <div className="small">
              표적 {card.target_segment}, 앵커 {card.anchor_items.join(", ")}
            </div>
          </div>
        ))}
      </div>
      <p className="small">A_brand는 브랜드 효과 측정용 문구이고 실제 제품이나 계획이 아닙니다. 앵커가 다른 카드끼리의 라벨 차이는 안의 차이가 아닙니다.</p>

      <h2 id="explore">탐색 출력 표본</h2>
      <div className="band">
        <p>
          <strong>{stage4.explore.marking}</strong> 실제 소비자에게 확인하지 않았고 쓸모도 재지 않았습니다.
        </p>
      </div>
      <p>
        후보 카드마다 저장된 Terra 이유 문장을 Terra 호출 한 번으로 묶었습니다. 숫자 규칙, 차단 패턴, 페르소나 문장이나 이유 원문과 긴 조각을 공유하는 문장은 코드가 뺍니다. 패턴은 나열된 형태만 잡습니다. 합성 문장을 심는 필터 시험은 {num("stage4.explore_filter.passed")}/{num("stage4.explore_filter.total")} 통과했고 시험하지 않은 표현은 통과할 수 있습니다. 문장이 일반적이고 카드 문구를 되풀이하는 편입니다.
      </p>
      <div className="card-grid">
        {exploreCards.map((card) => (
          <ExploreCard card={card} key={card} />
        ))}
      </div>
      <div className="table-wrap" tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th>안</th>
              <th className="num">읽은 이유</th>
              {EXPLORE_SECTIONS.map((s) => (
                <th className="num" key={s.id}>
                  {s.label}
                </th>
              ))}
              <th className="num">페르소나 겹침</th>
              <th className="num">이유 원문 겹침</th>
              <th className="num">이 실행의 호출</th>
              <th className="num">앞 실행(demo7)의 비용</th>
            </tr>
          </thead>
          <tbody>
            {exploreCards.map((card) => (
              <tr key={card}>
                <td>{card}</td>
                <td className="num">{stage4.explore.cards[card].reasons_read}</td>
                {EXPLORE_SECTIONS.map((s) => (
                  <td className="num" key={s.id}>
                    {num(`stage4.explore8.${card}.${s.id}.kept`)}
                  </td>
                ))}
                <td className="num">{stage4.explore.cards[card].echo.persona_echo}</td>
                <td className="num">{stage4.explore.cards[card].echo.reason_echo}</td>
                <td className="num">{num(`stage4.explore8.${card}.calls_this_card`)}</td>
                <td className="num">{usd(num(`stage4.explore.${card}.cost_usd`))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small">상한은 반대 이유와 끌리는 점 각 5개, 세그먼트 가설 3개, 문항 초안 5개입니다. 코드가 뺀 문장은 카드마다 상한 초과 {stage4.explore.cards.A.dropped_by_code.over_limit}건입니다.</p>
      <Caveats items={caveats(["stage4.explore.A.cost_usd", "stage4.explore_filter.total"])} />
      <SourceLine files={sources(["stage4.explore8.A.objections.kept", "stage4.explore.A.cost_usd", "stage4.explore_filter.total"])} keys="stage4.explore8.*, stage4.explore.*, stage4.explore_filter.*" />

      <h2 id="duel">실측 대결: 건강검진 기록</h2>
      <HealthCheckDecision />
      <p>실측 200명이 오면 같은 응답자의 패널 값과 묶어 R1과 겨루고, 결과를 건강검진으로 보고서와 원장에 적습니다. 규칙의 신뢰도는 <a href="/results#duel">측정 결과 9절</a>에 있습니다.</p>
      <DuelStatusTable />
      <h3>이 실행의 기록 (results/stage4/{demo.run_id}/real_results.json)</h3>
      <ul>
        {stage4.real_results.lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <p className="small">항목별 결과는 싣지 않습니다. 같은 표본에서 접힘 시드만 바꿔도 항목별 keep이 크게 달라져(<a href="/results#same-sample">측정 결과 9절</a>) 한 번의 항목별 결과를 인용할 수 없습니다.</p>
      <p className="small">받는 파일: 실측 파일은 respondent_id, age_band, sex, weight, ever, weekly, carb, concept_X(1~5), 있으면 unit_id, 패널 파일은 respondent_id, p_ever, p_weekly, p_carb, p_concept_X입니다. 대용 파일은 git이 무시하는 폴더에 있고 이 사이트와 저장소에는 집계만 있습니다.</p>
      <Caveats items={caveats(["stage4.demo8.ingest.report_status"])} />
      <SourceLine files={sources(["stage4.demo8.ingest.report_status"])} keys="stage4.demo8.ingest.*" />

      <h2>실측 200명 배분</h2>
      <p>{a.choose_note} 시스템은 설문을 보내지 않습니다(<code>sent: {String(demo.questionnaire.sent)}</code>). 발주는 조사 담당자가 합니다.</p>
      <div className="table-wrap" tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th>집단</th>
              <th className="num">n</th>
              <th className="num">오차 ±pp</th>
              <th>계산</th>
            </tr>
          </thead>
          <tbody>
            {[
              { label: "전체", r: a.overall },
              { label: `표적 ${a.target_segment}`, r: a.target },
              { label: "나머지", r: a.rest },
              ...a.cells.map((c) => ({ label: SEGMENT[c.cell] ?? c.cell, r: c })),
              { label: "6칸 균등이었다면 칸당", r: a.six_cells_even },
              { label: "12칸 균등이었다면 칸당", r: a.twelve_cells_even },
              { label: "카드 4장의 첫 카드만", r: a.first_card_each },
            ].map(({ label, r }) => (
              <tr key={label}>
                <td>{label}</td>
                <td className="num">{r.n}</td>
                <td className="num">{fixed(r.margin_pp, 1)}</td>
                <td className="num">{r.arithmetic}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>조사 단위 군집을 고려한 유효 표본</h3>
      <div className="table-wrap" tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th>항목</th>
              <th className="num">단위당 m</th>
              <th className="num">ICC</th>
              <th className="num">설계 효과</th>
              <th className="num">유효 n</th>
              <th className="num">오차 ±pp</th>
            </tr>
          </thead>
          <tbody>
            {a.design_effects.map((d) => (
              <tr key={d.item}>
                <td>{d.item}</td>
                <td className="num">{d.unit_size}</td>
                <td className="num">{d.icc}</td>
                <td className="num">{d.design_effect}</td>
                <td className="num">{d.effective_n}</td>
                <td className="num">{fixed(d.margin_pp, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul>
        <li>
          이 표가 답하는 것: 큰 차이의 방향이 맞는가, 패널이 틀린 곳이 어디인가. 12칸을 재는 표가 아닙니다. 전국 값을 읽을 때는 가중치를 씁니다.
        </li>
        <li>{a.benchmark_note}</li>
        <li>
          칸별 인원은 설정의 고정 값과 카드의 표적 세그먼트로 정합니다. 패널 값으로 칸 인원을 계산한 배분은 비례 배분과 실질적 차이가 없었습니다(<a href="/results#allocation">측정 결과 7절</a>).
        </li>
        <li>초대 명단이나 응답 여부를 받지 못하면 「보정 불가, 직접 추정만」으로 씁니다. 코드는 이 조건을 확인하지 못하고 담당자가 파일을 넣기 전에 확인합니다.</li>
      </ul>

      <h3>문항지 구성</h3>
      <p className="small">{demo.questionnaire.intro}</p>
      <div className="table-wrap" tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th>문항 id</th>
              <th>종류</th>
            </tr>
          </thead>
          <tbody>
            {demo.questionnaire.items.map((i) => (
              <tr key={i.id}>
                <td>
                  <code>{i.id}</code>
                </td>
                <td>{i.kind === "concept" ? "콘셉트" : i.kind === "anchor" ? "앵커" : "인구 특성"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small">앵커 문항은 KREI 조사의 A15, A19와 같은 문구로 표본 치우침을 점검합니다. KREI 문항 원문은 이 사이트에 싣지 않습니다.</p>
      <p className="small">이 문항지로는 응답자 단위 패널 값을 만들 수 없습니다. 인구 항목은 연령대, 성별, 거주 지역, 가구원 수뿐이고, 패널의 C1 페르소나 변수 9개 중 동 구분, 직업, 학력, 혼인 상태, 소득이 없으며 C2 허용 문항도 없습니다.</p>
      <ul className="small">
        {demo.questionnaire.fieldwork_rules.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>

      <h2>부록: 도구 호출 순서</h2>
      <p>순서는 코드가 정합니다. 선행 조건이 없으면 도구가 <code>blocked</code>를 돌려줍니다. 시간은 첫 기록에서 잰 초입니다.</p>
      <ReplaySteps steps={demo.steps as Step[]} />
      <p className="small">
        승인 기록 값: {demo.approval.approver}, {demo.approval.at}. 이 승인은 사람이 키보드에서 한 것이 아니라 작업 지시서의 예산 범위에 따른 시연 승인입니다.
      </p>

      <h2>부록: 앞 단계 규칙의 판정표</h2>
      <p>이 라벨은 앞 단계 규칙의 기록입니다. 결정에 쓰지 않습니다. {demo.verdict.header} 칸 라벨은 동결된 규칙 v2와 카드의 앵커로 정해지고, 규칙 v2는 답을 본 뒤에 썼습니다.</p>
      <VerdictTable rows={overall} />
      <details>
        <summary>세그먼트별 {demo.verdict.rows.length}행 보기</summary>
        <VerdictTable rows={demo.verdict.rows} />
      </details>
      <ul>
        <li>시연에서 A, B가 실측 전용이고 C가 방향만인 것은 carb 앵커 유무의 차이입니다. 안의 차이가 아닙니다.</li>
        <li>순서 사용이 허용된 칸은 {demo.verdict.any_order_allowed ? "있습니다" : "없습니다"}. 패널 원수치를 시장 수치로 쓰지 않습니다.</li>
      </ul>
      <details>
        <summary>판정 문장 {demo.verdict.sentences.length}개 보기 (코드 템플릿)</summary>
        <ul>
          {demo.verdict.sentences.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </details>

      <h3>실행 안의 진단 (정답과 무관한 잡음 점검)</h3>
      <div className="table-wrap" tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th>진단, pp</th>
              <th className="num">Terra</th>
              <th className="num">Luna</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>바꿔 쓴 차이 A - A_para</td>
              {models.map((m) => (
                <td className="num" key={m}>
                  {signed(num(`demo.${m}.noise_A_minus_A_para.mean`))} {ciText(interval(`demo.${m}.noise_A_minus_A_para.ci95`))}
                </td>
              ))}
            </tr>
            {pairs.map((p) => (
              <tr key={p}>
                <td>후보 차이 {p.replace("_minus_", " - ")}</td>
                {models.map((m) => (
                  <td className="num" key={m}>
                    {signed(num(`demo.${m}.gap.${p}.mean`))} {ciText(interval(`demo.${m}.gap.${p}.ci95`))} {bool(`demo.${m}.gap.${p}.distinguishable`) ? "구분" : "구분 불가"}
                  </td>
                ))}
              </tr>
            ))}
            {["A", "B", "C"].map((c) => (
              <tr key={c}>
                <td>{c} - 음성 대조</td>
                {models.map((m) => (
                  <td className="num" key={m}>
                    {signed(num(`demo.${m}.negative.${c}.mean`))} {ciText(interval(`demo.${m}.negative.${c}.ci95`))}
                  </td>
                ))}
              </tr>
            ))}
            <tr>
              <td>브랜드 표시 효과 A_brand - A</td>
              {models.map((m) => (
                <td className="num" key={m}>
                  {signed(num(`demo.${m}.brand.mean`))} {ciText(interval(`demo.${m}.brand.ci95`))} {bool(`demo.${m}.brand.exceeds_noise`) ? "잡음 초과" : "잡음 안"}
                </td>
              ))}
            </tr>
            <tr>
              <td>패널 내부 값 순서 (사용 불가)</td>
              {models.map((m) => (
                <td className="num" key={m}>
                  {any<string[]>(`demo.${m}.rank`).join(" > ")}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="small">
        잡음을 넘는 차이도 실측에서 보일 만한 크기라는 뜻은 아닙니다. 실측 200명 전체의 단일 비율 오차는 ±{num("demo.allocation.overall.margin_pp")}pp입니다. 바꿔 쓴 카드는 후보 A 하나뿐이라 이 잡음이 다른 후보에도 같다고 가정합니다. 이 실행의 추적 파일에는 절대값을 싣지 않고 쌍 차이만 남겼습니다. 앞 실행 demo~demo5의 추적 파일에는 숨긴 칸의 값이 남아 있어, 그 실행들에서 「절대값 숨김」은 보고서 본문에만 해당합니다.
      </p>

      <h3>왜 그럴 수 있나 (가설, 근거 아님)</h3>
      <ul>
        {hypotheses.map((s) => (
          <li key={s}>가설: {s}</li>
        ))}
      </ul>

      <Caveats items={caveats(demoKeys)} />
      <SourceLine files={sources(demoKeys)} keys="demo.*" />
    </>
  );
}
