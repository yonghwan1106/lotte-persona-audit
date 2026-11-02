"use client";

import { useState } from "react";
import { halfUp, spoken } from "@/lib/format";

export type GlassItem = { id: string; label: string; real: number; panel: number };

const FLOOR = 500; // zero on the shared scale, the inside bottom of both glasses
const FOOT = 16; // the thick glass under the liquid
const UNITS = 4.2; // user units per percentage point, shared by both glasses
const LEFT = 170;
const RIGHT = 512;
const HALF_TOP = 116;
const HALF_BOTTOM = 100;
const TOP = FLOOR - 100 * UNITS - 14;

const yOf = (pct: number) => FLOOR - pct * UNITS;
const halfAt = (y: number) => HALF_TOP + ((y - TOP) / (FLOOR + FOOT - TOP)) * (HALF_BOTTOM - HALF_TOP);

function outline(cx: number) {
  const bottom = FLOOR + FOOT;
  const wt = HALF_TOP;
  const wb = HALF_BOTTOM;
  return `M${cx - wt} ${TOP} L${cx - wb} ${bottom - 12} Q${cx - wb + 1} ${bottom} ${cx - wb + 14} ${bottom} L${cx + wb - 14} ${bottom} Q${cx + wb - 1} ${bottom} ${cx + wb} ${bottom - 12} L${cx + wt} ${TOP}`;
}

function inside(cx: number) {
  const wt = HALF_TOP - 6;
  const wb = halfAt(FLOOR) - 6;
  return `M${cx - wt} ${TOP} L${cx - wb} ${FLOOR - 8} Q${cx - wb + 1} ${FLOOR} ${cx - wb + 10} ${FLOOR} L${cx + wb - 10} ${FLOOR} Q${cx + wb - 1} ${FLOOR} ${cx + wb} ${FLOOR - 8} L${cx + wt} ${TOP} Z`;
}

const BUBBLES = [
  { dx: -74, r: 4, d: 5.2, delay: 0 },
  { dx: -52, r: 2.5, d: 3.9, delay: 1.6 },
  { dx: -30, r: 5.5, d: 6.1, delay: 0.8 },
  { dx: -10, r: 3, d: 4.4, delay: 2.7 },
  { dx: 12, r: 4.5, d: 5.6, delay: 1.1 },
  { dx: 34, r: 2.5, d: 4.1, delay: 3.4 },
  { dx: 56, r: 5, d: 5.9, delay: 2.1 },
  { dx: 78, r: 3, d: 4.7, delay: 0.4 },
];
const FIZZ = [
  { dx: -84, dy: 9, r: 3.5 },
  { dx: -62, dy: 16, r: 2.5 },
  { dx: -41, dy: 7, r: 4.5 },
  { dx: -18, dy: 19, r: 3 },
  { dx: 4, dy: 8, r: 3.5 },
  { dx: 27, dy: 15, r: 4 },
  { dx: 49, dy: 7, r: 2.5 },
  { dx: 70, dy: 18, r: 3.5 },
  { dx: 90, dy: 9, r: 3 },
];

function Glass({ id, cx, pct, fill, name, depth }: { id: string; cx: number; pct: number; fill: string; name: string; depth: number }) {
  const y = yOf(pct);
  const rise = pct * UNITS;
  return (
    <g>
      <clipPath id={`glass-${id}`}>
        <path d={inside(cx)} />
      </clipPath>
      <path d={`${outline(cx)} Z`} fill="#ffffff" />
      <g clipPath={`url(#glass-${id})`}>
        <g className="liquid-rise" style={{ "--rise": `${rise}px` } as React.CSSProperties}>
          <rect className="liquid-move" x={cx - HALF_TOP} width={HALF_TOP * 2} fill={fill} style={{ y, height: FLOOR + 40 - y } as React.CSSProperties} />
          <rect className="liquid-move" x={cx - HALF_TOP} width={HALF_TOP * 2} fill="#ffffff" opacity={0.45} style={{ y, height: 6 } as React.CSSProperties} />
          <g className="liquid-move" style={{ transform: `translateY(${y}px)` }}>
            {FIZZ.map((b, i) => (
              <circle key={i} cx={cx + b.dx} cy={b.dy} r={b.r} fill="#ffffff" opacity={0.72} />
            ))}
          </g>
        </g>
        <g className="bubbles" style={{ "--travel": `${-Math.max(0, rise - 16)}px` } as React.CSSProperties}>
          {BUBBLES.map((b, i) => (
            <circle key={i} cx={cx + b.dx} cy={FLOOR - 7} r={b.r} fill="#ffffff" style={{ animationDuration: `${b.d}s`, animationDelay: `${b.delay + depth}s` }} />
          ))}
        </g>
        <rect x={cx - HALF_TOP + 24} y={TOP} width={13} height={FLOOR - TOP} fill="#ffffff" opacity={0.26} />
      </g>
      <path d={outline(cx)} fill="none" stroke="#12323B" strokeWidth={3.5} strokeLinecap="round" strokeLinejoin="round" />
      <ellipse cx={cx} cy={TOP} rx={HALF_TOP} ry={9} fill="#ffffff" stroke="#12323B" strokeWidth={3.5} />
      <g className="number-rise" style={{ "--rise": `${rise}px` } as React.CSSProperties}>
        <text className="glass-number liquid-move" x={cx} textAnchor="middle" style={{ transform: `translateY(${y - 16}px)` }}>
          {halfUp(pct)}
          <tspan className="glass-unit">%</tspan>
        </text>
      </g>
      <text x={cx} y={FLOOR + FOOT + 38} textAnchor="middle" className="glass-name">
        {name}
      </text>
    </g>
  );
}

export function HeroGlasses({ items, initial }: { items: GlassItem[]; initial: string }) {
  const [selected, setSelected] = useState(initial);
  const item = items.find((i) => i.id === selected) ?? items[0];
  const gap = item.panel - item.real;
  const summary = spoken(`${item.label}: 실제 응답 ${halfUp(item.real)}%, GPT 패널 ${halfUp(item.panel)}%, 차이 ${halfUp(gap)}%⁠포인트. 패널 값은 시장 수치가 아닙니다.`);
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
      <svg viewBox="-16 0 696 566" role="img" aria-label={summary} className="glasses-svg">
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
            +{halfUp(gap)}
          </text>
          <text className="liquid-move gap-unit" x={bracketX} textAnchor="middle" style={{ transform: `translateY(${yPanel - 12}px)` }}>
            %⁠포인트
          </text>
        </g>
      </svg>
      <p className="glasses-caption">
        이미 있는 음료 행동을 잰 값입니다. <strong>패널 값은 시장 수치가 아닙니다.</strong> 실제 응답: KREI 식품소비행태조사 2025.
      </p>
      <p className="visually-hidden" aria-live="polite">
        {summary}
      </p>
    </div>
  );
}
