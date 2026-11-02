"use client";

import { useState } from "react";

export type GlassItem = { id: string; label: string; real: number; panel: number };

const BOTTOM = 500;
const UNITS = 4.2; // user units per percentage point, shared by both glasses
const LEFT = 170;
const RIGHT = 512;
const HALF_TOP = 116;
const HALF_BOTTOM = 100;
const TOP = BOTTOM - 100 * UNITS - 14;

const yOf = (pct: number) => BOTTOM - pct * UNITS;
// Half up, so that 54.05 reads 54.1 and the shown gap equals the difference of the shown numbers.
const one = (x: number) => (Math.round(x * 10 + 1e-6) / 10).toFixed(1);

function glassPath(cx: number, inset = 0) {
  const top = TOP + inset;
  const bottom = BOTTOM + 2 - inset;
  const wt = HALF_TOP - inset;
  const wb = HALF_BOTTOM - inset;
  return `M${cx - wt} ${top} L${cx - wb} ${bottom - 10} Q${cx - wb + 1} ${bottom} ${cx - wb + 12} ${bottom} L${cx + wb - 12} ${bottom} Q${cx + wb - 1} ${bottom} ${cx + wb} ${bottom - 10} L${cx + wt} ${top}`;
}

const BUBBLES = [
  { dx: -62, r: 3, d: 5.2, delay: 0 },
  { dx: -30, r: 2, d: 3.9, delay: 1.6 },
  { dx: -8, r: 4, d: 6.1, delay: 0.8 },
  { dx: 24, r: 2.5, d: 4.4, delay: 2.7 },
  { dx: 52, r: 3.5, d: 5.6, delay: 1.1 },
  { dx: 70, r: 2, d: 4.1, delay: 3.4 },
];

function Glass({ id, cx, pct, fill, name, depth }: { id: string; cx: number; pct: number; fill: string; name: string; depth: number }) {
  const y = yOf(pct);
  const rise = pct * UNITS;
  return (
    <g>
      <clipPath id={`glass-${id}`}>
        <path d={`${glassPath(cx, 5)} Z`} />
      </clipPath>
      <path d={`${glassPath(cx, 0)} Z`} fill="#ffffff" />
      <g clipPath={`url(#glass-${id})`}>
        <g className="liquid-rise" style={{ "--rise": `${rise}px` } as React.CSSProperties}>
          <rect className="liquid-move" x={cx - HALF_TOP} width={HALF_TOP * 2} fill={fill} style={{ y, height: BOTTOM + 40 - y } as React.CSSProperties} />
          <rect className="liquid-move" x={cx - HALF_TOP} width={HALF_TOP * 2} fill="#ffffff" opacity={0.35} style={{ y, height: 7 } as React.CSSProperties} />
        </g>
        <g className="bubbles" style={{ "--travel": `${-Math.max(0, rise - 18)}px` } as React.CSSProperties}>
          {BUBBLES.map((b, i) => (
            <circle key={i} cx={cx + b.dx} cy={BOTTOM - 8} r={b.r} fill="#ffffff" style={{ animationDuration: `${b.d}s`, animationDelay: `${b.delay + depth}s` }} />
          ))}
        </g>
        <rect x={cx - HALF_TOP + 22} y={TOP} width={13} height={BOTTOM - TOP} fill="#ffffff" opacity={0.24} />
      </g>
      <path d={glassPath(cx, 0)} fill="none" stroke="#12323B" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
      <g className="number-rise" style={{ "--rise": `${rise}px` } as React.CSSProperties}>
        <text className="glass-number liquid-move" x={cx} textAnchor="middle" style={{ transform: `translateY(${y - 16}px)` }}>
          {one(pct)}
          <tspan className="glass-unit">%</tspan>
        </text>
      </g>
      <text x={cx} y={BOTTOM + 40} textAnchor="middle" className="glass-name">
        {name}
      </text>
    </g>
  );
}

export function HeroGlasses({ items, initial }: { items: GlassItem[]; initial: string }) {
  const [selected, setSelected] = useState(initial);
  const item = items.find((i) => i.id === selected) ?? items[0];
  const gap = item.panel - item.real;
  const summary = `${item.label}: 실제 응답 ${one(item.real)}%, GPT 패널 ${one(item.panel)}%, 차이 ${one(gap)}%⁠포인트. 패널 값은 시장 수치가 아닙니다.`;
  const ticks = [0, 25, 50, 75, 100];
  const bracketX = (LEFT + RIGHT) / 2;
  const yReal = yOf(item.real);
  const yPanel = yOf(item.panel);

  return (
    <div className="glasses">
      <fieldset className="pill-group">
        <legend className="visually-hidden">측정 항목 고르기</legend>
        {items.map((option) => (
          <label key={option.id} className={option.id === selected ? "pill is-on" : "pill"}>
            <input type="radio" name="hero-item" value={option.id} checked={option.id === selected} onChange={() => setSelected(option.id)} />
            {option.label}
          </label>
        ))}
      </fieldset>
      <svg viewBox="0 0 680 556" role="img" aria-label={summary} className="glasses-svg">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={40} x2={52} y1={yOf(t)} y2={yOf(t)} stroke="#567079" strokeWidth={2} />
            <text x={34} y={yOf(t) + 6} textAnchor="end" className="glass-tick">
              {t}
            </text>
          </g>
        ))}
        <rect x={51} width={2} y={yOf(100)} height={100 * UNITS} fill="#567079" />
        <Glass id="real" cx={LEFT} pct={item.real} fill="#00829B" name="실제 응답" depth={0} />
        <Glass id="panel" cx={RIGHT} pct={item.panel} fill="#F0A81E" name="GPT 패널" depth={0.4} />
        <g className="gap-mark">
          <rect className="liquid-move" x={LEFT + 96} width={RIGHT - LEFT - 192} height={2} fill="#12323B" style={{ y: yReal } as React.CSSProperties} />
          <rect className="liquid-move" x={bracketX - 1.5} width={3} fill="#7A5200" style={{ y: yPanel, height: yReal - yPanel } as React.CSSProperties} />
          <rect className="liquid-move" x={bracketX - 40} width={RIGHT - bracketX - 56} height={2} fill="#7A5200" style={{ y: yPanel } as React.CSSProperties} />
          <text className="liquid-move gap-number" x={bracketX} textAnchor="middle" style={{ transform: `translateY(${yPanel - 34}px)` }}>
            +{one(gap)}
          </text>
          <text className="liquid-move gap-unit" x={bracketX} textAnchor="middle" style={{ transform: `translateY(${yPanel - 12}px)` }}>
            %⁠포인트
          </text>
        </g>
      </svg>
      <p className="glasses-caption">
        이미 있는 음료 행동을 잰 값입니다. <strong>패널 값은 시장 수치가 아닙니다.</strong>
      </p>
      <p className="visually-hidden" aria-live="polite">
        {summary}
      </p>
    </div>
  );
}
