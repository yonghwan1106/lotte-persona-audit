import { TipLayer } from "@/components/viz/TipLayer";

type Tone = "water" | "glass" | "mist" | "deep";

/** A scene: one finding, one visual, a change of background. The composition is chosen per scene by className. */
export function Scene({ id, tone = "water", className = "", children }: { id?: string; tone?: Tone; className?: string; children: React.ReactNode }) {
  return (
    <section id={id} className={`scene tone-${tone} ${className}`}>
      <div className="scene-in">{children}</div>
    </section>
  );
}

/** Tables, caveats and sources stay one click away, so that no evidence leaves the page. */
export function Evidence({ summary = "근거와 표 보기", children }: { summary?: string; children: React.ReactNode }) {
  return (
    <details className="evidence">
      <summary>{summary}</summary>
      <div className="evidence-body">{children}</div>
    </details>
  );
}

/** A chart: an image with a written summary. Its table sits in the scene's evidence. */
export function Figure({ label, className = "", children }: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <TipLayer className={`figure-box ${className}`} label={label}>
      {children}
    </TipLayer>
  );
}

/** One drawing for each width, so that type stays the same size instead of shrinking with the viewBox. */
export function TwoUp({ wide, narrow }: { wide: React.ReactNode; narrow: React.ReactNode }) {
  return (
    <>
      <div className="only-wide">{wide}</div>
      <div className="only-narrow">{narrow}</div>
    </>
  );
}

export function Glossary() {
  return (
    <p className="glossary">
      표기: Terra와 Luna는 패널을 돌린 두 모델(gpt-6.1-terra, gpt-6-luna)입니다. C1은 인구 특성만 쓴 페르소나, C2는 음료가 아닌 허용 문항을 더한 페르소나입니다. E3은 패널 그대로, E2는 실제 200명 평균을 전체 평균 쪽으로 줄인 값, E4~E6은 패널을 실제 200명으로 보정한 값, R1은 패널 없이 같은 200명으로 맞춘 나이·성별 회귀입니다. row는 행 단위로, cluster는 조사 단위 통째로 뽑은 추출입니다. pp는 %⁠포인트입니다. keep은 대결에서 패널 값을 남기는 쪽으로 나온 결과입니다.
    </p>
  );
}

export function PersonMark({ x, y, color = "#12323B", scale = 1 }: { x: number; y: number; color?: string; scale?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`} aria-hidden="true">
      <circle cx={0} cy={-13} r={7} fill={color} />
      <path d="M-11 9 C-11 -3 -6 -5 0 -5 C6 -5 11 -3 11 9 Z" fill={color} />
    </g>
  );
}
