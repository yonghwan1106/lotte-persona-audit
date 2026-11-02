import { Figure, TwoUp } from "@/components/viz/Scene";

function Drawing({ width, keeps }: { width: number; keeps: number }) {
  const narrow = width < 500;
  const box = narrow ? 104 : 156;
  const mid = width / 2;
  const noteLines = narrow ? [`연속 통과 ${keeps}회`, "필요한 횟수 합의 전"] : [`연속 통과 ${keeps}회, 필요한 횟수 합의 전`];
  return (
    <svg viewBox={`0 0 ${width} 158`} className="gate-svg">
      <rect x={1.5} y={46} width={box} height={62} fill="none" stroke="#F0A81E" strokeWidth={3} />
      <text x={box / 2} y={83} textAnchor="middle" className="gate-label">
        패널 값
      </text>
      <rect x={box} y={75} width={mid - box - 5} height={4} fill="#9FBAC0" />
      <rect x={mid - 5} y={10} width={10} height={124} fill="#ffffff" />
      <text x={mid} y={154} textAnchor="middle" className="gate-note">
        닫힘
      </text>
      <rect x={mid + 5} y={75} width={width - box - mid - 6} height={4} fill="#567079" />
      <rect x={width - box - 1.5} y={46} width={box} height={62} fill="none" stroke="#9FBAC0" strokeWidth={3} />
      <text x={width - box / 2} y={83} textAnchor="middle" className="gate-label">
        보고서
      </text>
      {noteLines.map((line, i) => (
        <text key={line} x={mid + 16} y={24 + i * 17} className="gate-note">
          {line}
        </text>
      ))}
    </svg>
  );
}

export function ReportGate({ keeps }: { keeps: number }) {
  return (
    <Figure label={`패널 값이 보고서로 가는 길은 닫혀 있습니다. 조사 단위를 온전히 둔 연속 통과 기록은 ${keeps}회이고, 필요한 횟수는 아직 합의하지 않았습니다.`} className="gate">
      <TwoUp wide={<Drawing width={720} keeps={keeps} />} narrow={<Drawing width={358} keeps={keeps} />} />
    </Figure>
  );
}
