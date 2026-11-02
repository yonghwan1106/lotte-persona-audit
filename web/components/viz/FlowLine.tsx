import { Figure, PersonMark, TwoUp } from "@/components/viz/Scene";

type Zone = "panel" | "real" | "person";
type Station = { id: string; label: string; note: string; zone: Zone; built: boolean };
type Person = { label: string; note: string; at: number };

const STATIONS: Station[] = [
  { id: "card", label: "콘셉트 카드", note: "담당자가 넣음", zone: "panel", built: true },
  { id: "scan", label: "패널 훑기", note: "구현됨", zone: "panel", built: true },
  { id: "action", label: "안별 제안", note: "구현됨", zone: "panel", built: true },
  { id: "survey", label: "실제 200명 조사", note: "설계, 표와 문항지만 구현됨", zone: "real", built: false },
  { id: "health", label: "건강검진", note: "설계, 대용 자료로만 실행", zone: "real", built: false },
  { id: "decide", label: "사람의 결정", note: "설계", zone: "person", built: false },
];

const CENTER = [72, 298, 440, 766, 906, 1046];
const PEOPLE: (Person & { x: number })[] = [
  { label: "비용 승인", note: "터미널 명령, 1회 사용", at: 1, x: 185 },
  { label: "실측 대상 선택", note: "설계", at: 3, x: 548 },
  { label: "조사 발주", note: "설계", at: 3, x: 652 },
  { label: "최종 결정", note: "설계", at: 5, x: 1046 },
];

const BELT: Record<Zone, string> = { panel: "#F0A81E", real: "#00829B", person: "#12323B" };

function Icon({ id, x, y }: { id: string; x: number; y: number }) {
  const ink = "#12323B";
  if (id === "card")
    return (
      <g transform={`translate(${x} ${y})`} fill="none" stroke={ink} strokeWidth={2}>
        <rect x={-13} y={-9} width={26} height={18} />
        <line x1={-8} x2={8} y1={-3} y2={-3} />
        <line x1={-8} x2={3} y1={3} y2={3} />
      </g>
    );
  if (id === "scan")
    return (
      <g transform={`translate(${x} ${y})`} fill="#B87C00">
        {[-12, -4, 4, 12].flatMap((dx) => [-5, 3].map((dy) => <circle key={`${dx}${dy}`} cx={dx} cy={dy} r={2.6} />))}
      </g>
    );
  if (id === "action")
    return (
      <g transform={`translate(${x} ${y}) rotate(-6)`} fill="none" stroke="#7A5200" strokeWidth={2}>
        <rect x={-15} y={-8} width={30} height={16} rx={3} />
        <line x1={-8} x2={8} y1={0} y2={0} />
      </g>
    );
  if (id === "survey")
    return (
      <g transform={`translate(${x} ${y})`} fill="#00829B">
        {[-14, -7, 0, 7, 14].flatMap((dx) => [-6, 0, 6].map((dy) => <circle key={`${dx}${dy}`} cx={dx} cy={dy} r={2.2} />))}
      </g>
    );
  if (id === "health") return <polyline transform={`translate(${x} ${y})`} points="-16,1 -7,1 -3,-8 3,9 7,1 16,1" fill="none" stroke="#00829B" strokeWidth={2.2} strokeLinejoin="round" />;
  return <polyline transform={`translate(${x} ${y})`} points="-11,0 -3,8 12,-8" fill="none" stroke={ink} strokeWidth={3.5} strokeLinejoin="round" strokeLinecap="round" />;
}

function Wide() {
  const beltY = 240;
  const blockTop = 112;
  const blockH = 106;
  const blockW = 132;
  return (
    <svg viewBox="0 0 1150 300" width="100%">
      {/* belt, coloured by whose work it carries */}
      <rect x={5} y={beltY - 7} width={515} height={14} fill={BELT.panel} />
      <rect x={520} y={beltY - 7} width={455} height={14} fill={BELT.real} />
      <rect x={975} y={beltY - 7} width={170} height={14} fill={BELT.person} />
      {Array.from({ length: 24 }, (_, i) => (
        <path key={i} d={`M${22 + i * 47} ${beltY - 4} l6 4 l-6 4`} fill="none" stroke={i >= 11 ? "#ffffff" : "#12323B"} strokeWidth={2} />
      ))}
      {Array.from({ length: 16 }, (_, i) => (
        <circle key={i} cx={30 + i * 73} cy={beltY + 16} r={7} fill="none" stroke="#567079" strokeWidth={2} />
      ))}
      {PEOPLE.map((p) => (
        <g key={p.label}>
          <text x={p.x} y={22} textAnchor="middle" className="flow-person">
            {p.label}
          </text>
          <text x={p.x} y={40} textAnchor="middle" className="flow-note">
            {p.note === "설계" ? "설계" : "터미널 1회"}
          </text>
          <PersonMark x={p.x} y={68} />
          <line x1={p.x} x2={p.x} y1={80} y2={p.at === 5 ? blockTop : beltY - 7} stroke="#12323B" strokeWidth={1.5} />
        </g>
      ))}
      {STATIONS.map((s, i) => {
        const x = CENTER[i];
        const [first, second] = s.note.split(", ");
        return (
          <g key={s.id} data-tip={`${s.label}: ${s.note}`}>
            <line x1={x} x2={x} y1={blockTop + blockH} y2={beltY - 7} stroke="#12323B" strokeWidth={2} />
            <rect x={x - blockW / 2} y={blockTop} width={blockW} height={blockH} fill="#ffffff" stroke="#12323B" strokeWidth={s.built ? 2.5 : 1.5} strokeDasharray={s.built ? undefined : "6 5"} />
            <Icon id={s.id} x={x} y={blockTop + 22} />
            <text x={x} y={blockTop + 56} textAnchor="middle" className="flow-label">
              {s.label}
            </text>
            <text x={x} y={blockTop + 75} textAnchor="middle" className="flow-note">
              {first}
            </text>
            {second ? (
              <text x={x} y={blockTop + 92} textAnchor="middle" className="flow-note">
                {second}
              </text>
            ) : null}
          </g>
        );
      })}
      <text x={5} y={290} className="flow-zone">
        패널이 하는 일
      </text>
      <text x={520} y={290} className="flow-zone">
        실제 응답으로 하는 일
      </text>
      <text x={1144} y={290} textAnchor="end" className="flow-zone">
        사람이 하는 일
      </text>
    </svg>
  );
}

function Narrow() {
  const rows: ({ kind: "station"; s: Station; i: number } | { kind: "person"; p: Person })[] = [];
  STATIONS.forEach((s, i) => {
    PEOPLE.filter((p) => p.at === i).forEach((p) => rows.push({ kind: "person", p }));
    rows.push({ kind: "station", s, i });
  });
  let y = 8;
  const placed = rows.map((row) => {
    const top = y;
    y += row.kind === "station" ? 84 : 56;
    return { row, top };
  });
  const total = y + 8;
  const beltX = 22;
  return (
    <svg viewBox={`0 0 358 ${total}`} width="100%">
      {placed.map(({ row, top }, n) => {
        const next = placed[n + 1]?.top ?? total - 8;
        const zone = row.kind === "station" ? row.s.zone : row.p.at >= 5 ? "person" : row.p.at >= 3 ? "real" : "panel";
        return <rect key={`b${n}`} x={beltX - 6} y={top} width={12} height={next - top} fill={BELT[zone]} />;
      })}
      {placed.map(({ row, top }) => {
        if (row.kind === "person") {
          return (
            <g key={row.p.label}>
              <line x1={beltX} x2={64} y1={top + 28} y2={top + 28} stroke="#12323B" strokeWidth={1.5} />
              <PersonMark x={78} y={top + 30} />
              <text x={100} y={top + 25} className="flow-person">
                {row.p.label}
              </text>
              <text x={100} y={top + 43} className="flow-note">
                {row.p.note}
              </text>
            </g>
          );
        }
        const { s } = row;
        return (
          <g key={s.id}>
            <line x1={beltX} x2={46} y1={top + 40} y2={top + 40} stroke="#12323B" strokeWidth={2} />
            <rect x={46} y={top + 6} width={306} height={70} fill="#ffffff" stroke="#12323B" strokeWidth={s.built ? 2.5 : 1.5} strokeDasharray={s.built ? undefined : "6 5"} />
            <Icon id={s.id} x={76} y={top + 41} />
            <text x={106} y={top + 36} className="flow-label">
              {s.label}
            </text>
            <text x={106} y={top + 57} className="flow-note">
              {s.note}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function FlowLine() {
  return (
    <Figure label="서비스 흐름. 콘셉트 카드, 패널 훑기, 안별 제안, 실제 200명 조사, 건강검진, 사람의 결정 순서입니다. 사람은 비용 승인, 실측 대상 선택, 조사 발주, 최종 결정의 네 곳에서 정합니다. 실제 조사, 건강검진, 사람의 결정과 세 사람 표시는 설계이고, 비용 승인은 터미널 명령으로 작은 실행 한 번에 썼습니다." className="flow">
      <TwoUp wide={<Wide />} narrow={<Narrow />} />
    </Figure>
  );
}

/** The table behind the drawing. */
export function FlowTable() {
  return (
    <div className="table-wrap" tabIndex={0}>
      <table>
        <thead>
          <tr>
            <th>순서</th>
            <th>단계</th>
            <th>지금 상태</th>
            <th>이 앞에서 사람이 정하는 것</th>
          </tr>
        </thead>
        <tbody>
          {STATIONS.map((s, i) => (
            <tr key={s.id}>
              <td>{i + 1}</td>
              <td>{s.label}</td>
              <td>{s.note}</td>
              <td>
                {PEOPLE.filter((p) => p.at === i)
                  .map((p) => `${p.label}(${p.note})`)
                  .join(", ") || "없음"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
