"use client";

import { useState } from "react";

export type Step = {
  seconds: number;
  event: string;
  tool?: string;
  text?: string;
  detail?: Record<string, unknown>;
};

const CARD_ROLE: Record<string, string> = {
  candidate: "후보",
  paraphrase: "바꿔 쓴 카드",
  brand: "브랜드 표시 카드",
  negative_control: "음성 대조",
};

function summary(step: Step): { head: string; body?: string } {
  const d = (step.detail ?? {}) as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  switch (step.event) {
    case "user_message":
      return { head: "요청", body: step.text };
    case "intake_check":
      return { head: "접수 점검 (코드)", body: `통과. 근거 ${d.by}: 등록 카드를 가리키는 요청은 패턴과 Decisions를 건너뜁니다. 이 경로의 약점은 공격 기록에 있습니다.` };
    case "tool_call":
      if (step.tool === "validate_card") return { head: `validate_card 호출`, body: `카드 ${d.card_id}` };
      if (step.tool === "plan_run") return { head: "plan_run 호출", body: `${d.n_personas}명, ${(d.models as string[]).join(", ")}, 페르소나 없는 조건 ${d.include_c0 ? "포함" : "제외"}` };
      return { head: `${step.tool} 호출` };
    case "tool_output":
      if (step.tool === "validate_card") return { head: `validate_card 결과: ${d.status}`, body: `카드 ${d.card_id}, ${CARD_ROLE[d.role] ?? d.role}. 제거 ${d.removed.length}건, 제외 ${d.excluded.length}건` };
      if (step.tool === "plan_run") {
        const plan = d.plan;
        return { head: `plan_run 결과: ${d.status}`, body: `${plan.calls_total.toLocaleString("en-US")}건, 예상 ${plan.expected_usd} USD, 상한 ${plan.cost_cap_usd} USD, 약 ${plan.estimated_minutes}분. ${plan.formula}. 호출은 하지 않았고 사람 승인이 필요합니다.` };
      }
      if (step.tool === "run_panel") return { head: `run_panel 결과: ${d.status}`, body: `이 재실행의 새 패널 호출 ${(d.stages as { counts: { called: number } }[]).reduce((sum, s) => sum + s.counts.called, 0)}건, 앞 단계 캐시 사용, 비용 ${d.spent_this_run_usd} USD. 파일럿 ${d.pilot_n}명 음성 대조 구분: ${d.pilot_passed ? "통과" : "실패"}` };
      if (step.tool === "diagnose_run") return { head: "diagnose_run 결과", body: "무정답 진단을 코드가 계산했습니다. 값은 아래 진단 표에 있습니다." };
      if (step.tool === "decide_verdict") return { head: `decide_verdict 결과: ${d.status}`, body: `판정 문장 ${d.sentences}개를 코드 템플릿으로 냈습니다.` };
      if (step.tool === "allocate_real_sample") return { head: `allocate_real_sample 결과: ${d.status}`, body: `표적 ${d.target_segment}` };
      if (step.tool === "build_questionnaire") return { head: `build_questionnaire 결과: ${d.status}`, body: `문항 ${d.items}개. 설문은 보내지 않습니다.` };
      if (step.tool === "explore_card") return { head: `explore_card 결과: ${d.status}`, body: `카드 ${d.card}. 가설 문장을 남겼고, 페르소나 문장과 이유 원문의 겹침 점검 ${d.echo_check_passed ? "통과" : "실패"}. 문장은 아래 탐색 출력 표본에 있습니다.` };
      if (step.tool === "write_ledger") return { head: `write_ledger 결과: ${d.status}`, body: `매니페스트 ${String(d.manifest_sha256).slice(0, 16)}…` };
      return { head: `${step.tool} 결과` };
    case "approval_requested":
      return { head: "승인 요청", body: `계획 해시 ${String(d.plan_hash).slice(0, 16)}…` };
    case "approval_pending":
      return { head: "승인 대기", body: "실행이 여기서 멈추고 상태를 저장합니다." };
    case "approval_recorded":
      return { head: "승인 기록", body: `승인자 값: ${d.approver}. 사람이 키보드에서 한 승인이 아닙니다.` };
    case "approval_granted":
      return { head: "같은 실행으로 재개" };
    case "narrator_output":
      return { head: `서술 전문가 출력: ${d.accepted ? "숫자 규칙 통과" : "기각"}`, body: `가설 문장 ${(d.sentences as string[]).length}개. 근거가 아닙니다.` };
    case "final":
      return { head: `최종 상태: ${d.status}`, body: d.note };
    default:
      return { head: step.event };
  }
}

export function ReplaySteps({ steps }: { steps: Step[] }) {
  const [shown, setShown] = useState(steps.length);
  const visible = steps.slice(0, shown);
  return (
    <div>
      <div className="form-row">
        <button type="button" onClick={() => setShown(1)}>
          처음부터 보기
        </button>
        <button type="button" onClick={() => setShown(Math.max(1, shown - 1))} disabled={shown <= 1}>
          이전 단계
        </button>
        <button type="button" onClick={() => setShown(Math.min(steps.length, shown + 1))} disabled={shown >= steps.length}>
          다음 단계
        </button>
        <button type="button" onClick={() => setShown(steps.length)} disabled={shown >= steps.length}>
          전체 보기
        </button>
        <span className="char-count" aria-live="polite">
          {shown} / {steps.length}
        </span>
      </div>
      <ol className="steps">
        {visible.map((step, i) => {
          const { head, body } = summary(step);
          return (
            <li key={i}>
              <span className="step-no">{i + 1}</span>
              <div>
                <div className="step-head">
                  {head} <span className="step-time">+{step.seconds.toFixed(1)}초</span>
                </div>
                {body ? <div>{body}</div> : null}
                {step.detail ? (
                  <details>
                    <summary>기록 값</summary>
                    <pre>{JSON.stringify(step.detail, null, 1)}</pre>
                  </details>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
