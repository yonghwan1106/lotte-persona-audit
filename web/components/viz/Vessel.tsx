/** A plain container for a fictional demo concept: a can or a PET bottle with one letter. No brand, no label art. */
export function Vessel({ letter, kind = "can", dim = false, stamp }: { letter: string; kind?: "can" | "pet"; dim?: boolean; stamp?: string }) {
  const body = dim ? "#D5E0E3" : "#ffffff";
  const ink = dim ? "#567079" : "#12323B";
  return (
    <svg viewBox="0 0 150 216" className="vessel" aria-hidden="true">
      {kind === "can" ? (
        <g stroke={ink} strokeWidth={2.5} fill={body} strokeLinejoin="round">
          <path d="M46 12 L104 12 L116 32 L116 186 L104 206 L46 206 L34 186 L34 32 Z" />
          <path d="M34 32 L116 32 M34 186 L116 186" fill="none" />
          <path d="M60 12 L90 12" stroke={ink} strokeWidth={5} />
        </g>
      ) : (
        <g stroke={ink} strokeWidth={2.5} fill={body} strokeLinejoin="round">
          <rect x={60} y={4} width={30} height={18} rx={3} />
          <path d="M62 22 L88 22 L88 34 C88 44 112 50 112 72 L112 192 Q112 206 98 206 L52 206 Q38 206 38 192 L38 72 C38 50 62 44 62 34 Z" />
          <path d="M38 92 L112 92 M38 178 L112 178" fill="none" />
        </g>
      )}
      <text x={75} y={148} textAnchor="middle" className="vessel-letter" fill={ink}>
        {letter}
      </text>
      {stamp ? (
        <g transform="translate(75 66) rotate(-7)">
          <rect x={-68} y={-16} width={136} height={32} rx={4} fill="#FFF6DF" stroke="#7A5200" strokeWidth={2.5} />
          <text textAnchor="middle" y={6} className="vessel-stamp">
            {stamp}
          </text>
        </g>
      ) : null}
    </svg>
  );
}
