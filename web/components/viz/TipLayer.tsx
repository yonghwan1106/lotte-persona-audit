"use client";

import { useRef, useState } from "react";
import { spoken } from "@/lib/format";

/** Shows the data-tip of the mark under the pointer. It adds nothing a table does not hold: every value is in the scene's evidence. */
export function TipLayer({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  const box = useRef<HTMLDivElement | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const move = (event: React.PointerEvent<HTMLDivElement>) => {
    const target = (event.target as Element).closest?.("[data-tip]");
    const frame = box.current?.getBoundingClientRect();
    const text = target?.getAttribute("data-tip");
    if (!text || !frame) {
      setTip(null);
      return;
    }
    setTip({ x: Math.max(0, Math.min(event.clientX - frame.left + 12, frame.width - 240)), y: event.clientY - frame.top + 14, text });
  };
  return (
    <div ref={box} role="img" aria-label={spoken(label)} className={className} onPointerMove={move} onPointerDown={move} onPointerLeave={() => setTip(null)}>
      {children}
      {tip ? (
        <div className="chart-tip" style={{ left: tip.x, top: tip.y }}>
          {tip.text}
        </div>
      ) : null}
    </div>
  );
}
