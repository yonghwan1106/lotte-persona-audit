"use client";

import { useState } from "react";
import { smallestGap, type DetectableParams } from "@/lib/detectable";
import { spoken } from "@/lib/format";

const MIN = 100;
const MAX = 1570;

export function SampleSlider({ params, marks }: { params: DetectableParams; marks: { perCard: number; total: number; gap: number }[] }) {
  const [n, setN] = useState(MIN);
  const gap = smallestGap(n, params);
  const base = 50;
  const left = (v: number) => `${((v - MIN) / (MAX - MIN)) * 100}%`;
  const valueText = spoken(`카드당 ${n.toLocaleString("en-US")}명, 전체 ${(n * 2).toLocaleString("en-US")}명, 가려낼 수 있는 가장 작은 차이 ${gap.toFixed(1)}%⁠포인트`);

  return (
    <div className="slider">
      <div className="slider-read">
        <div className="slider-gap">
          {gap.toFixed(1)}
          <span>%⁠포인트</span>
        </div>
        <p>
          한 카드에 <strong>{n.toLocaleString("en-US")}명</strong>, 두 카드 합쳐 <strong>{(n * 2).toLocaleString("en-US")}명</strong>이면 이보다 작은 차이는 가려내기 어렵습니다.
        </p>
      </div>

      <div role="img" aria-label={`두 막대 그림. ${valueText}. 응답 50% 기준의 계산입니다.`} className="slider-bars">
        <div className="slider-bar-row">
          <span>안 A</span>
          <div className="slider-track">
            <i style={{ width: `${base}%` }} />
          </div>
        </div>
        <div className="slider-bar-row">
          <span>안 B</span>
          <div className="slider-track">
            <i style={{ width: `${base}%` }} />
            <b style={{ left: `${base}%`, width: `${gap}%` }} />
          </div>
        </div>
        <div className="slider-axis" aria-hidden="true">
          <span>0</span>
          <span>50</span>
          <span>100%</span>
        </div>
        <p className="slider-key">
          <i aria-hidden="true" />
          진한 칸: 이만큼 벌어져야 가려낼 수 있는 차이
        </p>
        <p className="slider-note">안 A를 50%로 둔 계산 그림이며, 어느 안의 예상값도 아닙니다. 유의수준 5%, 검정력 80%입니다.</p>
      </div>

      <div className="slider-control">
        <label htmlFor="sample-n">카드당 인원을 끌어 보세요</label>
        <input id="sample-n" type="range" min={MIN} max={MAX} step={1} value={n} onChange={(event) => setN(Number(event.target.value))} aria-valuetext={valueText} />
        <div className="slider-marks">
          {marks.map((mark) => (
            <button key={mark.perCard} type="button" style={{ left: left(mark.perCard) }} className={n === mark.perCard ? "slider-mark is-on" : "slider-mark"} onClick={() => setN(mark.perCard)} aria-label={spoken(`카드당 ${mark.perCard.toLocaleString("en-US")}명으로 옮기기, 전체 ${mark.total.toLocaleString("en-US")}명이면 ${mark.gap}%⁠포인트`)}>
              <strong>전체 {mark.total.toLocaleString("en-US")}명</strong>
              <span>{mark.gap}%⁠포인트</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
