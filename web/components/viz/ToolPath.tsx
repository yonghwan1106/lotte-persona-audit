"use client";

import { useState } from "react";
import { stepSummary, type Step } from "@/components/ReplaySteps";

type Stop = { id: string; label: string; who: string; person?: boolean; match: (s: Step) => boolean };

const STOPS: Stop[] = [
  { id: "ask", label: "요청 접수", who: "금지 요청 패턴을 코드로 점검합니다", match: (s) => s.event === "user_message" || s.event === "intake_check" },
  { id: "validate", label: "카드 점검", who: "카드 6장을 한 장씩 코드로 점검합니다", match: (s) => s.tool === "validate_card" },
  { id: "plan", label: "계획", who: "호출 수와 비용 상한을 계산하고, 호출은 아직 하지 않습니다", match: (s) => s.tool === "plan_run" },
  { id: "approve", label: "승인", who: "여기서 멈춥니다. 이 시연의 승인은 사람이 하지 않았습니다", person: true, match: (s) => s.event.startsWith("approval") },
  { id: "panel", label: "패널", who: "패널을 돌리거나 저장된 답을 읽습니다", match: (s) => s.tool === "run_panel" && !s.event.startsWith("approval") },
  { id: "diagnose", label: "진단", who: "정답과 무관한 잡음을 코드가 계산합니다", match: (s) => s.tool === "diagnose_run" },
  { id: "verdict", label: "제안", who: "규칙이 판정표와 문장을 만듭니다", match: (s) => s.tool === "decide_verdict" },
  { id: "narrate", label: "서술", who: "모델이 쓴 문장은 숫자 규칙을 통과해야 하고, 가설로만 남습니다", match: (s) => s.tool === "narrate_verdict" || s.event === "narrator_output" },
  { id: "explore", label: "탐색", who: "반대 이유와 문항 초안을 가설 문장으로 냅니다", match: (s) => s.tool === "explore_card" },
  { id: "allocate", label: "200명 배분", who: "설문을 보내지 않고 표만 냅니다", match: (s) => s.tool === "allocate_real_sample" },
  { id: "questionnaire", label: "문항지", who: "문항지 파일을 만듭니다", match: (s) => s.tool === "build_questionnaire" },
  { id: "ledger", label: "원장", who: "실행 기록을 해시와 함께 남깁니다", match: (s) => s.tool === "write_ledger" },
  { id: "final", label: "끝", who: "완료 상태는 모델의 주장이 아니라 코드 상태로 정합니다", match: (s) => s.event === "final" },
];

export function ToolPath({ steps }: { steps: Step[] }) {
  const [at, setAt] = useState(0);
  const stop = STOPS[at];
  const here = steps.filter(stop.match);
  const seconds = here.length ? here[0].seconds : 0;
  return (
    <div className="toolpath">
      <ol className="toolpath-line" aria-label="도구 호출 순서">
        {STOPS.map((s, i) => (
          <li key={s.id} className={`${i === at ? "is-on" : ""} ${i < at ? "is-past" : ""} ${s.person ? "is-person" : ""}`}>
            <button type="button" onClick={() => setAt(i)} aria-current={i === at ? "step" : undefined}>
              <span className="toolpath-dot">{i + 1}</span>
              <span className="toolpath-label">{s.label}</span>
            </button>
          </li>
        ))}
      </ol>
      <div className="toolpath-detail" aria-live="polite">
        <h3>
          {at + 1}. {stop.label} <span>{seconds.toFixed(1)}초</span>
        </h3>
        <p>{stop.who}</p>
        <ul>
          {here
            .filter((s) => s.event !== "tool_call" || here.length === 1)
            .map((s, i) => {
              const { head, body } = stepSummary(s);
              return (
                <li key={i}>
                  <strong>{head}</strong> {body}
                </li>
              );
            })}
        </ul>
        <div className="toolpath-buttons">
          <button type="button" onClick={() => setAt(Math.max(0, at - 1))} disabled={at === 0}>
            이전 단계
          </button>
          <button type="button" className="primary" onClick={() => setAt(Math.min(STOPS.length - 1, at + 1))} disabled={at === STOPS.length - 1}>
            다음 단계
          </button>
        </div>
      </div>
    </div>
  );
}
