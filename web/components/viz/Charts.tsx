// Charts drawn on the server. Each is an image with a written summary and takes its numbers as props from the sheet or web/data.
import { COLOR } from "@/lib/colors";
import { Figure, TwoUp } from "@/components/viz/Scene";

const INK = "#12323B";
const INK2 = "#3E5B64";
const INK3 = "#567079";
const GRID = "#D9E7EA";
const AXIS = "#9FBAC0";

export type LadderStep = { id: string; label: string; note: string; value: number; fill: string; tab?: string };

/** The error ladder. Lengths share one scale from zero; the last two rungs are bracketed as not separable. */
function LadderDrawing({ steps, width, gapText }: { steps: LadderStep[]; width: number; gapText: string }) {
  const narrow = width < 500;
  const left = 0;
  const right = narrow ? width - 58 : width - 340;
  const scale = (v: number) => (v / 16) * (right - left);
  const rowH = narrow ? 92 : 78;
  const top = 8;
  const barH = 30;
  const height = top + rowH * steps.length + 34;
  const bracketFrom = top + rowH * 2 + (narrow ? 30 : 10);
  const bracketTo = top + rowH * 3 + (narrow ? 30 + barH : 10 + barH);
  const bracketX = narrow ? width - 6 : 590;
  const gapLines = gapText.split(", 범위 ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%">
      {[0, 5, 10, 15].map((t) => (
        <g key={t}>
          <line x1={scale(t)} x2={scale(t)} y1={top} y2={height - 26} stroke={t === 0 ? AXIS : GRID} />
          <text x={scale(t)} y={height - 8} textAnchor={t === 0 ? "start" : "middle"} className="axis-text">
            {t}
          </text>
        </g>
      ))}
      {steps.map((s, i) => {
        const y = top + rowH * i;
        const barY = narrow ? y + 30 : y + 10;
        return (
          <g key={s.id} data-tip={`${s.label}: ${s.value}%⁠포인트`}>
            {narrow ? (
              <text x={0} y={y + 20} className="ladder-label">
                {s.label}
              </text>
            ) : null}
            <path d={`M${left} ${barY} H${scale(s.value) - 4} q4 0 4 4 V${barY + barH - 4} q0 4 -4 4 H${left} Z`} fill={s.fill} />
            {s.tab ? <rect x={left} y={barY} width={14} height={barH} fill={s.tab} /> : null}
            <text x={scale(s.value) + 10} y={barY + 23} className="ladder-value">
              {s.value}
            </text>
            {narrow ? (
              <text x={0} y={barY + barH + 18} className="ladder-note">
                {s.note}
              </text>
            ) : (
              <>
                <text x={scale(s.value) + 74} y={barY + 14} className="ladder-label">
                  {s.label}
                </text>
                <text x={scale(s.value) + 74} y={barY + 33} className="ladder-note">
                  {s.note}
                </text>
              </>
            )}
          </g>
        );
      })}
      {narrow ? (
        <g>
          <path d={`M${bracketX - 8} ${bracketFrom} H${bracketX} V${bracketTo} H${bracketX - 8}`} fill="none" stroke={INK} strokeWidth={2} />
          <text x={bracketX - 14} y={(bracketFrom + bracketTo) / 2 - 14} textAnchor="end" className="ladder-bracket">
            구별되지 않음
          </text>
          {gapLines.map((line, i) => (
            <text key={line} x={bracketX - 14} y={(bracketFrom + bracketTo) / 2 + 6 + i * 17} textAnchor="end" className="ladder-note">
              {line}
            </text>
          ))}
        </g>
      ) : (
        <g>
          <path d={`M${bracketX - 12} ${bracketFrom - 4} H${bracketX} V${bracketTo + 4} H${bracketX - 12}`} fill="none" stroke={INK} strokeWidth={2} />
          <text x={bracketX + 14} y={(bracketFrom + bracketTo) / 2} className="ladder-bracket">
            구별되지 않음
          </text>
          <text x={bracketX + 14} y={(bracketFrom + bracketTo) / 2 + 22} className="ladder-note">
            {gapText}
          </text>
        </g>
      )}
    </svg>
  );
}

export function ErrorLadder({ steps, gapText }: { steps: LadderStep[]; gapText: string }) {
  const summary = `12칸 평균 오차 사다리, 낮을수록 실제에 가깝습니다. ${steps.map((s) => `${s.label} ${s.value}%⁠포인트`).join(", ")}. 마지막 두 값은 구별되지 않습니다. ${gapText}`;
  return (
    <Figure label={summary} className="ladder">
      <TwoUp wide={<LadderDrawing steps={steps} width={1000} gapText={gapText} />} narrow={<LadderDrawing steps={steps} width={358} gapText={gapText} />} />
    </Figure>
  );
}

export type AgeRow = { band: string; real: number; panel: number };

/** One small multiple. All three panels share the 0 to 100 scale of the hero glasses. */
export function AgePanel({ title, rows }: { title: string; rows: AgeRow[] }) {
  const w = 340;
  const h = 268;
  const l = 34;
  const r = 66;
  const t = 12;
  const b = 34;
  const x = (i: number) => l + (i / (rows.length - 1)) * (w - l - r);
  const y = (v: number) => t + (1 - v / 100) * (h - t - b);
  const realLine = rows.map((row, i) => `${x(i)},${y(row.real)}`).join(" ");
  const panelLine = rows.map((row, i) => `${x(i)},${y(row.panel)}`).join(" ");
  const area = `${panelLine} ${[...rows].reverse().map((row, i) => `${x(rows.length - 1 - i)},${y(row.real)}`).join(" ")}`;
  const end = rows[rows.length - 1];
  const first = rows[0];
  return (
    <div className="age-panel">
      <h3>{title}</h3>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%">
        {[0, 50, 100].map((v) => (
          <g key={v}>
            <line x1={l} x2={w - r} y1={y(v)} y2={y(v)} stroke={v === 0 ? AXIS : GRID} />
            <text x={l - 6} y={y(v) + 4} textAnchor="end" className="axis-text">
              {v}
            </text>
          </g>
        ))}
        <polygon points={area} fill={COLOR.yuzu} opacity={0.28} />
        <polyline points={realLine} fill="none" stroke={COLOR.real} strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
        <polyline points={panelLine} fill="none" stroke={COLOR.panel} strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
        {rows.map((row, i) => (
          <g key={row.band} data-tip={`${row.band}: 실제 응답 ${row.real.toFixed(1)}%, 패널 ${row.panel.toFixed(1)}%, 차이 +${(row.panel - row.real).toFixed(1)}%⁠포인트`}>
            <rect x={x(i) - 22} y={t} width={44} height={h - t - b} fill="transparent" />
            <circle cx={x(i)} cy={y(row.real)} r={4} fill={COLOR.real} stroke="#fff" strokeWidth={2} />
            <circle cx={x(i)} cy={y(row.panel)} r={4} fill={COLOR.panel} stroke="#fff" strokeWidth={2} />
            <text x={x(i)} y={h - b + 18} textAnchor="middle" className="axis-text">
              {row.band.replace("세 이상", "+").replace("세", "").replace("~", "~")}
            </text>
          </g>
        ))}
        <text x={x(rows.length - 1) + 9} y={y(end.panel) + 4} className="end-label">
          패널 {end.panel.toFixed(0)}
        </text>
        <text x={x(rows.length - 1) + 9} y={y(end.real) + 4} className="end-label">
          실제 {end.real.toFixed(0)}
        </text>
        <text x={x(0) + 8} y={Math.max(y(first.panel) - 10, 12)} className="end-label-quiet">
          {first.panel.toFixed(0)}
        </text>
      </svg>
    </div>
  );
}

export function Key({ items }: { items: { label: string; color: string; shape?: "line" | "dot" | "area" }[] }) {
  return (
    <div className="chart-key">
      {items.map((item) => (
        <span key={item.label}>
          <svg width="20" height="12" aria-hidden="true">
            {item.shape === "area" ? <rect width="20" height="12" fill={item.color} opacity={0.28} /> : item.shape === "dot" ? <circle cx={10} cy={6} r={4.5} fill={item.color} /> : <line x1={0} x2={20} y1={6} y2={6} stroke={item.color} strokeWidth={3} />}
          </svg>
          {item.label}
        </span>
      ))}
    </div>
  );
}

export type SlopeRow = { id: string; label: string; real_rank: number; panel_rank: number; real_share: number; panel_share: number };

function SlopeDrawing({ rows, width, emphasis }: { rows: SlopeRow[]; width: number; emphasis: number }) {
  const narrow = width < 500;
  const labelW = narrow ? 104 : 172;
  const top = 34;
  const step = narrow ? 30 : 31;
  const height = top + step * rows.length + 6;
  const x1 = labelW;
  const x2 = width - labelW;
  const y = (rank: number) => top + (rank - 0.5) * step;
  const isBig = (row: SlopeRow) => Math.abs(row.panel_rank - row.real_rank) >= emphasis;
  const order = [...rows].sort((a, b) => Number(isBig(a)) - Number(isBig(b)));
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%">
      <text x={x1} y={16} textAnchor="middle" className="slope-head">
        실제 순위
      </text>
      <text x={x2} y={16} textAnchor="middle" className="slope-head">
        패널 순위
      </text>
      {order.map((row) => {
        const big = isBig(row);
        const up = row.panel_rank < row.real_rank;
        const color = big ? (up ? COLOR.panel : COLOR.real) : AXIS;
        return (
          <g key={row.id} data-tip={`${row.label}: 실제 ${row.real_rank}위 ${row.real_share.toFixed(1)}%, 패널 ${row.panel_rank}위 ${row.panel_share.toFixed(1)}%`}>
            <line x1={x1} x2={x2} y1={y(row.real_rank)} y2={y(row.panel_rank)} stroke={color} strokeWidth={big ? 3 : 1.5} />
            <circle cx={x1} cy={y(row.real_rank)} r={big ? 5 : 3.5} fill={color} />
            <circle cx={x2} cy={y(row.panel_rank)} r={big ? 5 : 3.5} fill={color} />
            <text x={x1 - 10} y={y(row.real_rank) + 5} textAnchor="end" className={big ? "slope-label is-big" : "slope-label"}>
              {row.label} {row.real_rank}
            </text>
            <text x={x2 + 10} y={y(row.panel_rank) + 5} className={big ? "slope-label is-big" : "slope-label"}>
              {row.panel_rank} {row.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function SlopeChart({ rows, label, emphasis = 4 }: { rows: SlopeRow[]; label: string; emphasis?: number }) {
  return (
    <Figure label={label} className="slope">
      <TwoUp wide={<SlopeDrawing rows={rows} width={760} emphasis={emphasis} />} narrow={<SlopeDrawing rows={rows} width={358} emphasis={emphasis} />} />
    </Figure>
  );
}

export type GenderRow = { id: string; label: string; real: number; realCi: [number, number]; panel: number; panelCi: [number, number]; opposite: boolean; zeroInReal: boolean };

function GenderDrawing({ rows, width }: { rows: GenderRow[]; width: number }) {
  const narrow = width < 500;
  const labelW = narrow ? 0 : 188;
  const rowH = narrow ? 112 : 96;
  const top = 8;
  const left = labelW + 12;
  const right = width - 12;
  const domain: [number, number] = [-10, 10];
  const x = (v: number) => left + ((v - domain[0]) / (domain[1] - domain[0])) * (right - left);
  const height = top + rowH * rows.length + 46;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%">
      {[-10, -5, 0, 5, 10].map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={top} y2={height - 42} stroke={t === 0 ? INK3 : GRID} strokeWidth={t === 0 ? 1.5 : 1} />
          <text x={x(t)} y={height - 26} textAnchor="middle" className="axis-text">
            {t > 0 ? `+${t}` : t}
          </text>
        </g>
      ))}
      <text x={x(0)} y={height - 8} textAnchor="middle" className="axis-text">
        여성 - 남성, %⁠포인트
      </text>
      {rows.map((row, i) => {
        const y0 = top + rowH * i;
        const yReal = y0 + (narrow ? 46 : 32);
        const yPanel = yReal + 26;
        const panelColor = row.opposite ? COLOR.grape : COLOR.panel;
        return (
          <g key={row.id}>
            <text x={0} y={narrow ? y0 + 22 : y0 + 44} className="gender-label">
              {row.label}
              {narrow && row.opposite ? ", 방향 반대" : ""}
            </text>
            <g data-tip={`${row.label}, 실제 응답 ${row.real > 0 ? "+" : ""}${row.real.toFixed(1)} [${row.realCi[0].toFixed(1)}, ${row.realCi[1].toFixed(1)}]`}>
              <rect x={left} y={yReal - 11} width={right - left} height={22} fill="transparent" />
              <line x1={x(row.realCi[0])} x2={x(row.realCi[1])} y1={yReal} y2={yReal} stroke={COLOR.real} strokeWidth={3} strokeLinecap="round" />
              <circle cx={x(row.real)} cy={yReal} r={6} fill={COLOR.real} stroke="#fff" strokeWidth={2} />
              <text x={x(row.realCi[1]) + 76 > width ? x(row.realCi[0]) - 10 : x(row.realCi[1]) + 10} y={yReal + 5} textAnchor={x(row.realCi[1]) + 76 > width ? "end" : "start"} className="gender-value">
                실제 {row.real > 0 ? "+" : ""}
                {row.real.toFixed(1)}
              </text>
            </g>
            <g data-tip={`${row.label}, 패널 ${row.panel.toFixed(1)} [${row.panelCi[0].toFixed(1)}, ${row.panelCi[1].toFixed(1)}]`}>
              <rect x={left} y={yPanel - 11} width={right - left} height={22} fill="transparent" />
              <line x1={x(row.panelCi[0])} x2={x(row.panelCi[1])} y1={yPanel} y2={yPanel} stroke={panelColor} strokeWidth={3} strokeLinecap="round" />
              {row.opposite ? <rect x={x(row.panel) - 6} y={yPanel - 6} width={12} height={12} fill={panelColor} stroke="#fff" strokeWidth={2} transform={`rotate(45 ${x(row.panel)} ${yPanel})`} /> : <circle cx={x(row.panel)} cy={yPanel} r={6} fill={panelColor} stroke="#fff" strokeWidth={2} />}
              <text x={row.opposite ? x(row.panelCi[0]) - 10 : x(row.panelCi[1]) + 10} y={yPanel + 5} textAnchor={row.opposite ? "end" : "start"} className="gender-value">
                패널 {row.panel.toFixed(1)}
                {row.opposite && !narrow ? ", 방향 반대" : ""}
              </text>
            </g>
          </g>
        );
      })}
    </svg>
  );
}

export function GenderDumbbell({ rows, label }: { rows: GenderRow[]; label: string }) {
  return (
    <Figure label={label} className="gender">
      <TwoUp wide={<GenderDrawing rows={rows} width={820} />} narrow={<GenderDrawing rows={rows} width={358} />} />
    </Figure>
  );
}

/** A strip of squares, one per run or one per rule label. */
export function Strip({ cells, label, className = "" }: { cells: { color: string; hollow?: boolean; tip?: string }[]; label: string; className?: string }) {
  return (
    <div className={`strip ${className}`} role="img" aria-label={label}>
      {cells.map((cell, i) => (
        <i key={i} title={cell.tip} style={cell.hollow ? { boxShadow: `inset 0 0 0 2px ${cell.color}` } : { background: cell.color }} />
      ))}
    </div>
  );
}

export function Waffle({ groups, label }: { groups: { name: string; n: number; color: string; note?: string }[]; label: string }) {
  return (
    <div role="img" aria-label={label} className="waffle">
      {groups.map((group) => (
        <div key={group.name} className="waffle-group">
          <div className="waffle-name">
            <strong>{group.name}</strong> {group.n}명{group.note ? <span> {group.note}</span> : null}
          </div>
          <div className="waffle-dots">
            {Array.from({ length: group.n }, (_, i) => (
              <i key={i} style={{ background: group.color }} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export const CHART = { INK, INK2, INK3, GRID, AXIS };
