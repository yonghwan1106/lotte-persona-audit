import { Figure, TwoUp } from "@/components/viz/Scene";

const YUZU = "#F0A81E";
const PIPE = "#9FBAC0";
const FIZZ = [0.08, 0.17, 0.29, 0.41, 0.53, 0.66, 0.78, 0.91];

/** Panel liquid stops at a closed door. The strip below counts passes in a row, with no agreed length yet. */
function Drawing({ width, keeps }: { width: number; keeps: number }) {
  const narrow = width < 500;
  const left = 2;
  const door = narrow ? 232 : 640;
  const doorW = narrow ? 14 : 20;
  const pipeTop = narrow ? 62 : 74;
  const pipeH = narrow ? 58 : 84;
  const pipeEnd = narrow ? 292 : 836;
  const pageX = pipeEnd;
  const pageW = narrow ? 60 : 110;
  const pageH = narrow ? 78 : 118;
  const pageY = pipeTop + pipeH / 2 - pageH / 2;
  const scaleY = narrow ? 204 : 252;
  const height = narrow ? 268 : 316;
  const steps = narrow ? 6 : 8;
  const stepW = (door - 14) / (steps - 1);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="gate-svg">
      {/* the pipe up to the door, full of panel liquid */}
      <rect x={left} y={pipeTop} width={door - left} height={pipeH} fill={YUZU} />
      {FIZZ.filter((f) => f > (narrow ? 0.6 : 0.3)).map((f, i) => (
        <circle key={f} cx={left + f * (door - left)} cy={pipeTop + pipeH * (i % 2 ? 0.28 : 0.74)} r={i % 3 === 0 ? 5 : 3.5} fill="#ffffff" opacity={0.72} />
      ))}
      <path d={`M${left} ${pipeTop} H${door} M${left} ${pipeTop + pipeH} H${door}`} stroke="#ffffff" strokeWidth={3} fill="none" />
      <text x={left + (narrow ? 12 : 24)} y={pipeTop + pipeH / 2 + (narrow ? 6 : 9)} className="gate-in-liquid">
        패널 절대값
      </text>

      {/* the empty pipe after the door */}
      <path d={`M${door + doorW} ${pipeTop} H${pipeEnd} M${door + doorW} ${pipeTop + pipeH} H${pipeEnd}`} stroke={PIPE} strokeWidth={3} fill="none" strokeDasharray="7 7" />

      {/* the door */}
      <rect x={door} y={pipeTop - (narrow ? 26 : 34)} width={doorW} height={pipeH + (narrow ? 52 : 68)} fill="#ffffff" />
      <text x={door + doorW / 2} y={pipeTop - (narrow ? 32 : 42)} textAnchor="middle" className="gate-closed">
        닫힘
      </text>

      {/* the report body */}
      <rect x={pageX} y={pageY} width={pageW} height={pageH} fill="none" stroke="#ffffff" strokeWidth={2.5} />
      {[0.26, 0.44, 0.62].map((f) => (
        <line key={f} x1={pageX + 12} x2={pageX + pageW - 12} y1={pageY + pageH * f} y2={pageY + pageH * f} stroke={PIPE} strokeWidth={2} />
      ))}
      <text x={pageX + pageW / 2} y={pageY + pageH + (narrow ? 20 : 26)} textAnchor="middle" className="gate-label">
        {narrow ? "보고서" : "보고서 본문"}
      </text>

      {/* passes in a row */}
      <text x={left} y={scaleY - 22} className="gate-count">
        연속 통과 {keeps}회
      </text>
      <line x1={7} x2={door - 7} y1={scaleY} y2={scaleY} stroke={PIPE} strokeWidth={2} />
      {Array.from({ length: steps }, (_, i) => {
        const x = 7 + i * stepW;
        const last = i === steps - 1;
        return last ? (
          <text key={i} x={x} y={scaleY + 8} textAnchor="middle" className="gate-unknown">
            ?
          </text>
        ) : (
          <circle key={i} cx={x} cy={scaleY} r={i === 0 ? 7 : 5} fill={i === 0 ? YUZU : "#12323B"} stroke={i === 0 ? "#ffffff" : PIPE} strokeWidth={2} />
        );
      })}
      <text x={left} y={scaleY + 30} className="gate-note">
        필요한 횟수는 아직 합의하지 않았습니다
      </text>
      <text x={left} y={scaleY + 52} className="gate-note">
        한 번 이겨도 문은 열리지 않습니다
      </text>
    </svg>
  );
}

export function ReportGate({ keeps }: { keeps: number }) {
  return (
    <Figure label={`패널 절대값이 보고서 본문으로 가는 길은 문이 닫혀 있습니다. 조사 단위를 온전히 둔 연속 통과 기록은 ${keeps}회이고, 필요한 횟수는 아직 합의하지 않았습니다. 한 번 이겨도 문은 열리지 않습니다.`} className="gate">
      <TwoUp wide={<Drawing width={950} keeps={keeps} />} narrow={<Drawing width={358} keeps={keeps} />} />
    </Figure>
  );
}
