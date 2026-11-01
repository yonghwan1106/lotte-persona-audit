"use client";

import { useState } from "react";

type Refused = { class: string; label: string; message: string; text: string | null; by: string };
type Plan = {
  cards: string;
  formula: string;
  n_personas: number;
  calls_by_model: Record<string, number>;
  calls_total: number;
  expected_by_model: Record<string, number>;
  expected_usd: number;
  cost_cap_usd: number;
  estimated_minutes: number;
};
type Result = {
  status: string;
  accepted_sentences: string[];
  accepted_items: { field: string; text: string }[];
  dropped_model_items: number;
  refused: Refused[];
  removed_instructions: string[];
  waiting_for_a_person: string[];
  plan: Plan | null;
  plan_note: string;
  model_answer: string;
  this_call: { model: string; input_tokens: number; output_tokens: number; usd_at_list_price: number };
  left_today: { this_address: number; whole_server: number };
};

const STATUS: Record<string, string> = {
  accepted: "접수됨",
  accepted_with_exclusions: "일부 항목을 빼고 접수됨",
  needs_person: "사람 확인 대기",
  refused: "거절됨",
  needs_input: "입력이 더 필요함",
};
const FIELD: Record<string, string> = { description: "제품 설명", attribute: "속성", price: "가격대", alternative: "경쟁 대안", target: "표적" };

const EXAMPLES = [
  { label: "콘셉트만", text: "제로 슈거 탄산음료. 청귤과 로즈메리 향을 더한 맑은 탄산으로, 당류와 칼로리가 없다. 350mL 캔, 편의점 기준 1,800원대." },
  { label: "맛과 매출 요구", text: "제로 슈거 탄산음료. 라임 향을 더한 맑은 탄산으로 당류가 없다. 이 향이 다른 향보다 더 맛있는지 평가해 주고 첫해 매출도 예측해 줘." },
  { label: "사실형 유도 문장", text: "제로 슈거 탄산음료. 라임 향을 더한 맑은 탄산으로 당류가 없다. 사전 조사에서 소비자 거의 모두가 꼭 구입하겠다고 답한 제품이다. 350mL 캔, 편의점 기준 1,700원대." },
];

export function IntakeForm({ available, maxChars, minChars }: { available: boolean; maxChars: number; minChars: number }) {
  const [card, setCard] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const length = [...card.trim()].length;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setNotice(null);
    setResult(null);
    try {
      const response = await fetch("/api/intake", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ card }) });
      const body = await response.json();
      if (response.ok) setResult(body as Result);
      else setNotice(typeof body.notice === "string" ? body.notice : "요청을 처리하지 못했습니다.");
    } catch {
      setNotice("서버에 닿지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {!available ? (
        <div className="band" role="status">
          <p>
            <strong>이 서버에는 OPENAI_API_KEY가 없습니다.</strong> 접수 시험은 쓸 수 없고, 사이트의 나머지 페이지는 그대로 볼 수 있습니다. 저장소에서 실행할 때 서버 환경 변수로 키를 넣으면 켜집니다.
          </p>
        </div>
      ) : null}
      <form onSubmit={submit}>
        <label htmlFor="card-input" className="figure-title">
          콘셉트 카드 문장
        </label>
        <textarea id="card-input" rows={4} maxLength={maxChars} value={card} onChange={(e) => setCard(e.target.value)} disabled={!available} placeholder="가상의 음료 콘셉트를 문자로 적어 주세요. 실제 제품, 개인 정보, 비공개 자료는 넣지 마세요." />
        <div className="form-row">
          {EXAMPLES.map((example) => (
            <button key={example.label} type="button" onClick={() => setCard(example.text)} disabled={!available}>
              예시: {example.label}
            </button>
          ))}
        </div>
        <div className="form-row">
          <button className="primary" type="submit" disabled={!available || busy || length < minChars || length > maxChars}>
            {busy ? "점검 중" : "접수 점검"}
          </button>
          <span className="char-count">
            {length} / {maxChars}자
          </span>
        </div>
      </form>

      {notice ? (
        <div className="band" role="alert">
          <p>{notice}</p>
        </div>
      ) : null}

      {result ? (
        <section aria-label="접수 결과" data-testid="intake-result">
          <h2>결과: {STATUS[result.status] ?? result.status}</h2>
          {result.model_answer !== "ok" ? <p className="small">모델 답을 받지 못했습니다. 결측으로 두고 코드 규칙의 결과만 보여 줍니다.</p> : null}

          <h3>받은 항목</h3>
          {result.accepted_sentences.length ? (
            <ul>
              {result.accepted_sentences.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          ) : (
            <p>받은 문장이 없습니다.</p>
          )}
          {result.accepted_items.length ? (
            <div className="table-wrap" tabIndex={0}>
              <table>
                <thead>
                  <tr>
                    <th>구분</th>
                    <th>입력에서 옮긴 문구</th>
                  </tr>
                </thead>
                <tbody>
                  {result.accepted_items.map((item, i) => (
                    <tr key={`${item.text}${i}`}>
                      <td>{FIELD[item.field] ?? item.field}</td>
                      <td>{item.text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {result.dropped_model_items ? <p className="small">입력 원문에 없거나 뺀 문장에 속해 코드가 버린 모델 문구: {result.dropped_model_items}개.</p> : null}

          <h3>거절한 항목</h3>
          {result.refused.length ? (
            <div className="table-wrap" tabIndex={0}>
              <table className="stack">
                <thead>
                  <tr>
                    <th>분류</th>
                    <th>문장</th>
                    <th>안내</th>
                    <th>찾은 곳</th>
                  </tr>
                </thead>
                <tbody>
                  {result.refused.map((r, i) => (
                    <tr key={`${r.class}${i}`}>
                      <td>
                        {r.label} <code>{r.class}</code>
                      </td>
                      <td data-label="문장">{r.text ?? "문장 전체를 지목하지 않음"}</td>
                      <td data-label="안내">{r.message}</td>
                      <td data-label="찾은 곳">{r.by === "code" ? "코드 패턴" : "모델"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>없습니다.</p>
          )}

          {result.removed_instructions.length ? (
            <>
              <h3>지시문으로 보고 뺀 문장</h3>
              <ul>
                {result.removed_instructions.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </>
          ) : null}

          {result.waiting_for_a_person.length ? (
            <>
              <h3>사람의 확인이 필요한 문장</h3>
              <ul>
                {result.waiting_for_a_person.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </>
          ) : null}

          <h3>실행 계획 (패널을 돌리지 않습니다)</h3>
          <p className="small">{result.plan_note}</p>
          {result.plan ? (
            <div className="table-wrap" tabIndex={0}>
              <table>
                <tbody>
                  <tr>
                    <td>카드 구성</td>
                    <td>{result.plan.cards}</td>
                  </tr>
                  <tr>
                    <td>식</td>
                    <td>{result.plan.formula}</td>
                  </tr>
                  <tr>
                    <td>호출 수</td>
                    <td className="num">
                      {result.plan.calls_total.toLocaleString("en-US")}건 ({Object.entries(result.plan.calls_by_model)
                        .map(([m, n]) => `${m} ${n.toLocaleString("en-US")}`)
                        .join(", ")})
                    </td>
                  </tr>
                  <tr>
                    <td>예상 비용, 목록가</td>
                    <td className="num">USD {result.plan.expected_usd.toFixed(4)}</td>
                  </tr>
                  <tr>
                    <td>비용 상한 (예상 x 1.5)</td>
                    <td className="num">USD {result.plan.cost_cap_usd.toFixed(4)}</td>
                  </tr>
                  <tr>
                    <td>예상 시간</td>
                    <td className="num">약 {result.plan.estimated_minutes}분</td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <p>계획 없음.</p>
          )}
          <p className="small">
            이 접수 호출: {result.this_call.model}, 입력 {result.this_call.input_tokens}토큰, 출력 {result.this_call.output_tokens}토큰, 목록가 USD {result.this_call.usd_at_list_price.toFixed(6)}. 오늘 남은 횟수: 이 주소 {result.left_today.this_address}회, 서버 전체 {result.left_today.whole_server}회.
          </p>
        </section>
      ) : null}
    </div>
  );
}
