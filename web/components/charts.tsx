"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { COLOR } from "@/lib/colors";

const SURFACE = "#ffffff";
const INK = "#12323B";
const INK2 = "#3E5B64";
const MUTED = "#48656E";
const GRID = "#D9E7EA";
const AXIS = "#9FBAC0";

export type Mark = { x: number; lo?: number; hi?: number; fill: string; hollow?: boolean; small?: boolean };
export type DotRow = { label?: string; value?: string; marks?: Mark[]; link?: [number, number]; tip?: string; heading?: string };
export type RefLine = { x: number; label: string };

function useWidth(initial = 760) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(initial);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const measure = () => setWidth(Math.max(240, Math.round(node.getBoundingClientRect().width)));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

export function Legend({ items }: { items: { label: string; fill: string; hollow?: boolean; line?: boolean }[] }) {
  return (
    <div className="legend">
      {items.map((item) => (
        <span className="key" key={item.label}>
          <svg width="16" height="12" aria-hidden="true">
            {item.line ? <line x1="0" x2="16" y1="6" y2="6" stroke={item.fill} strokeWidth="2" /> : null}
            <circle cx="8" cy="6" r="4" fill={item.hollow ? SURFACE : item.fill} stroke={item.fill} strokeWidth={item.hollow ? 2 : 0} />
          </svg>
          {item.label}
        </span>
      ))}
    </div>
  );
}

/**
 * One row per estimate on one shared horizontal axis. Wide screens put the label and the value beside the plot,
 * narrow screens put them above it, so type stays the same size at every width.
 */
export function DotRows({
  rows,
  domain,
  ticks,
  refs = [],
  axisLabel,
  tickStyle = "plain",
  ariaLabel,
}: {
  rows: DotRow[];
  domain: [number, number];
  ticks: number[];
  refs?: RefLine[];
  axisLabel: string;
  tickStyle?: "plain" | "percent" | "signed";
  ariaLabel: string;
}) {
  const tickFormat = (v: number) => (tickStyle === "percent" ? `${v}%` : tickStyle === "signed" && v > 0 ? `+${v}` : String(v));
  const { ref, width } = useWidth();
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const wide = width >= 620;

  const longestLabel = Math.max(...rows.map((r) => (r.label ? r.label.length : 0)));
  const longestValue = Math.max(...rows.map((r) => (r.value ? r.value.length : 0)));
  const labelW = wide ? Math.min(250, longestLabel * 13 + 12) : 0;
  const valueW = wide ? Math.min(290, longestValue * 7.4 + 16) : 0;
  const narrowTwoTier = !wide && longestLabel * 13 + longestValue * 7.2 > width - 10;
  const rowH = wide ? 30 : narrowTwoTier ? 60 : 44;
  const headH = 28;
  const topPad = refs.length ? 20 : 4;
  const bottomPad = 44;
  const plotLeft = wide ? labelW : 16;
  const plotRight = width - (wide ? valueW : 18);
  const plotW = Math.max(40, plotRight - plotLeft);
  const xs = (v: number) => plotLeft + ((v - domain[0]) / (domain[1] - domain[0])) * plotW;

  const placed = useMemo(() => {
    let y = topPad;
    return rows.map((row) => {
      const top = y;
      y += row.heading ? headH : rowH;
      return { row, top };
    });
  }, [rows, rowH, topPad]);
  const plotBottom = placed.length ? placed[placed.length - 1].top + (placed[placed.length - 1].row.heading ? headH : rowH) : topPad;
  const height = plotBottom + bottomPad;

  const show = (text: string | undefined, x: number, y: number) => {
    if (!text) return;
    setTip({ x: Math.max(0, Math.min(x + 12, width - 280)), y: y + 14, text });
  };

  return (
    <div className="chart-box" ref={ref}>
      <svg width={width} height={height} role="img" aria-label={ariaLabel}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={xs(t)} x2={xs(t)} y1={topPad} y2={plotBottom} stroke={t === 0 ? AXIS : GRID} strokeWidth="1" />
            <text x={xs(t)} y={plotBottom + 16} textAnchor="middle" fontSize="12" fill={MUTED} style={{ fontVariantNumeric: "tabular-nums" }}>
              {tickFormat(t)}
            </text>
          </g>
        ))}
        <text x={plotLeft + plotW / 2} y={plotBottom + 34} textAnchor="middle" fontSize="12" fill={MUTED}>
          {axisLabel}
        </text>
        {refs.map((line) => {
          const x = xs(line.x);
          const nearRight = x > plotLeft + plotW * 0.6;
          return (
            <g key={line.label}>
              <line x1={x} x2={x} y1={topPad - 2} y2={plotBottom} stroke={INK2} strokeWidth="1" />
              <text x={x + (nearRight ? -4 : 4)} y={topPad - 8} textAnchor={nearRight ? "end" : "start"} fontSize="12" fill={INK2}>
                {line.label}
              </text>
            </g>
          );
        })}
        {placed.map(({ row, top }, index) => {
          if (row.heading) {
            return (
              <text key={`h${index}`} x={0} y={top + 19} fontSize="13.5" fontWeight="600" fill={INK}>
                {row.heading}
              </text>
            );
          }
          const midY = wide ? top + rowH / 2 : top + rowH - 11;
          const textY = wide ? midY + 4.5 : top + 15;
          const valueY = wide ? midY + 4.5 : narrowTwoTier ? top + 32 : top + 15;
          const open = (event: React.MouseEvent) => {
            const box = (event.currentTarget as SVGGElement).ownerSVGElement?.getBoundingClientRect();
            if (box) show(row.tip, event.clientX - box.left, event.clientY - box.top);
          };
          return (
            <g
              key={`r${index}`}
              onMouseMove={open}
              onMouseLeave={() => setTip(null)}
              onClick={open}
            >
              <rect x={0} y={top} width={width} height={rowH} fill="transparent" />
              {row.label ? (
                <text x={0} y={textY} fontSize="13.5" fill={INK}>
                  {row.label}
                </text>
              ) : null}
              {row.value ? (
                <text x={wide ? width : narrowTwoTier ? 0 : width} y={valueY} textAnchor={wide || !narrowTwoTier ? "end" : "start"} fontSize="12.5" fill={INK2} style={{ fontVariantNumeric: "tabular-nums" }}>
                  {row.value}
                </text>
              ) : null}
              {row.link ? <line x1={xs(row.link[0])} x2={xs(row.link[1])} y1={midY} y2={midY} stroke={AXIS} strokeWidth="2" /> : null}
              {(row.marks ?? []).map((mark, i) =>
                mark.lo !== undefined && mark.hi !== undefined ? <line key={`w${i}`} x1={xs(mark.lo)} x2={xs(mark.hi)} y1={midY} y2={midY} stroke={mark.fill} strokeWidth="2" strokeLinecap="round" /> : null,
              )}
              {(row.marks ?? []).map((mark, i) => (
                <circle key={`d${i}`} cx={xs(mark.x)} cy={midY} r={mark.small ? 3.5 : 5} fill={mark.hollow ? SURFACE : mark.fill} stroke={mark.hollow ? mark.fill : SURFACE} strokeWidth="2" />
              ))}
            </g>
          );
        })}
      </svg>
      {tip ? (
        <div className="chart-tip" style={{ left: tip.x, top: tip.y }}>
          {tip.text}
        </div>
      ) : null}
    </div>
  );
}

export type Pair = { d: number; ci: [number, number] };
export type MaeCell = {
  level: { row: Record<string, number>; cluster: Record<string, number> };
  minusE2: { row: Record<string, Pair>; cluster: Record<string, Pair> };
  minusR1: { row: Record<string, Pair>; cluster: Record<string, Pair> };
  floor: number;
};

const EST_LABEL: Record<string, string> = {
  E3: "E3 패널 원수치",
  E2: "E2 200명 축소 평균",
  E4: "E4 보정: 절편",
  E5: "E5 보정: 절편·기울기",
  E6: "E6 보정: 칸 잔차",
  R1: "R1 200명 나이·성별 회귀",
};
const EST_COLOR: Record<string, string> = { E3: COLOR.panel, E2: COLOR.real, R1: COLOR.real, E4: COLOR.calibrated, E5: COLOR.calibrated, E6: COLOR.calibrated };

function sg(x: number, digits = 2) {
  const t = Math.abs(x).toFixed(digits);
  if (Number(t) === 0) return t;
  return (x < 0 ? "-" : "+") + t;
}
function ci(p: [number, number], digits = 2) {
  return `[${sg(p[0], digits)}, ${sg(p[1], digits)}]`;
}

function niceTicks(lo: number, hi: number, step: number) {
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Math.round(v * 100) / 100);
  return out;
}

export function MaeExplorer({
  models,
  items,
  data,
}: {
  models: { id: string; label: string }[];
  items: { id: string; label: string }[];
  data: Record<string, Record<string, MaeCell>>;
}) {
  const [model, setModel] = useState(models[0].id);
  const [item, setItem] = useState(items[items.length - 1].id);
  const cell = data[model][item];

  const allPairs = useMemo(() => {
    const e2: Pair[] = [];
    const r1: Pair[] = [];
    for (const byItem of Object.values(data)) {
      for (const c of Object.values(byItem)) {
        for (const kind of ["row", "cluster"] as const) {
          e2.push(...Object.values(c.minusE2[kind]));
          r1.push(...Object.values(c.minusR1[kind]));
        }
      }
    }
    const range = (list: Pair[]) => [Math.min(...list.map((p) => p.ci[0])), Math.max(...list.map((p) => p.ci[1]))];
    return { e2: range(e2), r1: range(r1) };
  }, [data]);

  const levelRows: DotRow[] = ["E3", "E2", "E4", "E5", "E6", "R1"].map((e) => {
    const row = cell.level.row[e];
    const cluster = cell.level.cluster[e];
    const same = row === cluster;
    return {
      label: EST_LABEL[e],
      value: same ? `${row.toFixed(2)}pp` : `row ${row.toFixed(2)} · cluster ${cluster.toFixed(2)}`,
      marks: same ? [{ x: row, fill: EST_COLOR[e] }] : [{ x: cluster, fill: EST_COLOR[e], hollow: true }, { x: row, fill: EST_COLOR[e] }],
      tip: `${EST_LABEL[e]}: row 평균 ${row.toFixed(3)}pp, cluster 평균 ${cluster.toFixed(3)}pp`,
    };
  });

  const pairRows = (kindSet: { row: Record<string, Pair>; cluster: Record<string, Pair> }, order: string[]): DotRow[] => {
    const out: DotRow[] = [];
    for (const e of order) {
      for (const kind of ["row", "cluster"] as const) {
        const p = kindSet[kind][e];
        if (!p) continue;
        out.push({
          label: `${e} · ${kind}`,
          value: `${sg(p.d)} ${ci(p.ci)}`,
          marks: [{ x: p.d, lo: p.ci[0], hi: p.ci[1], fill: EST_COLOR[e], hollow: kind === "cluster" }],
          tip: `${EST_LABEL[e]}, ${kind} 추출: 차이 ${sg(p.d, 3)}pp, 95% 구간 ${ci(p.ci, 3)}`,
        });
      }
    }
    return out;
  };

  const e2Domain: [number, number] = [Math.floor(allPairs.e2[0]) - 1, Math.ceil(allPairs.e2[1]) + 1];
  const r1Domain: [number, number] = [Math.floor(allPairs.r1[0]) - 0.5, Math.ceil(allPairs.r1[1]) + 0.5];
  const itemLabel = items.find((i) => i.id === item)?.label ?? item;
  const modelLabel = models.find((m) => m.id === model)?.label ?? model;

  const keyLegend = [
    { label: "패널 원수치", fill: COLOR.panel },
    { label: "실제 200명만", fill: COLOR.real },
    { label: "패널 + 실제 200명", fill: COLOR.calibrated },
    { label: "채움 row, 빈 원 cluster", fill: MUTED, hollow: true },
  ];

  return (
    <div>
      <div className="controls">
        <label>
          조합
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          항목
          <select value={item} onChange={(e) => setItem(e.target.value)}>
            {items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="figure">
        <div className="figure-title">칸 오차 (cell MAE, 낮을수록 truth에 가깝습니다)</div>
        <div className="figure-sub">
          {modelLabel}, {itemLabel}, 실제 200명. 200회 추출의 평균입니다. 수치 시트에는 오차 수준 자체의 구간이 없어, 구간은 아래 쌍 차이로 봅니다.
        </div>
        <Legend items={keyLegend} />
        <DotRows
          ariaLabel={`칸 오차, ${modelLabel}, ${itemLabel}`}
          rows={levelRows}
          domain={[0, 20]}
          ticks={[0, 5, 10, 15, 20]}
          axisLabel="cell MAE (pp)"
          refs={[{ x: cell.floor, label: `noise floor ${cell.floor}pp` }]}
        />
      </div>

      <div className="figure">
        <div className="figure-title">같은 200명 R1과의 차이, 95% 구간 (0 왼쪽이면 R1보다 낮은 오차)</div>
        <div className="figure-sub">이것이 질문의 비교입니다. 구간이 0을 포함하면 구별되지 않습니다. 행마다 같은 추출 안에서 짝지은 차이입니다.</div>
        <DotRows
          ariaLabel={`R1과의 차이, ${modelLabel}, ${itemLabel}`}
          rows={pairRows(cell.minusR1, ["E4", "E5", "E6"])}
          domain={r1Domain}
          ticks={niceTicks(r1Domain[0], r1Domain[1], 2)}
          axisLabel="추정기 cell MAE - R1 cell MAE (pp)"
        />
      </div>

      <div className="figure">
        <div className="figure-title">E2와의 차이, 95% 구간 (약한 비교 상대입니다)</div>
        <div className="figure-sub">E2는 평평한 평균으로 수축하므로 나이 패턴만 있어도 이깁니다. R1 행이 그 점을 보여 줍니다. 표시선은 사전 등록 문구의 noise floor입니다.</div>
        <DotRows
          ariaLabel={`E2와의 차이, ${modelLabel}, ${itemLabel}`}
          rows={pairRows(cell.minusE2, ["E3", "R1", "E4", "E5", "E6"])}
          domain={e2Domain}
          ticks={niceTicks(e2Domain[0], e2Domain[1], 4)}
          axisLabel="추정기 cell MAE - E2 cell MAE (pp)"
          refs={[{ x: -cell.floor, label: `-${cell.floor}pp` }]}
        />
      </div>

      <details>
        <summary>표로 보기: {modelLabel}, {itemLabel}</summary>
        <div className="table-wrap" tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th>추정기</th>
                <th className="num">row MAE</th>
                <th className="num">cluster MAE</th>
                <th className="num">row - E2</th>
                <th className="num">cluster - E2</th>
                <th className="num">row - R1</th>
                <th className="num">cluster - R1</th>
              </tr>
            </thead>
            <tbody>
              {["E3", "E2", "E4", "E5", "E6", "R1"].map((e) => {
                const show = (p?: Pair) => (p ? `${sg(p.d, 3)} ${ci(p.ci, 3)}` : "없음");
                return (
                  <tr key={e}>
                    <td>{EST_LABEL[e]}</td>
                    <td className="num">{cell.level.row[e].toFixed(3)}</td>
                    <td className="num">{cell.level.cluster[e].toFixed(3)}</td>
                    <td className="num">{e === "E2" ? "기준" : show(cell.minusE2.row[e])}</td>
                    <td className="num">{e === "E2" ? "기준" : show(cell.minusE2.cluster[e])}</td>
                    <td className="num">{e === "R1" ? "기준" : show(cell.minusR1.row[e])}</td>
                    <td className="num">{e === "R1" ? "기준" : show(cell.minusR1.cluster[e])}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
