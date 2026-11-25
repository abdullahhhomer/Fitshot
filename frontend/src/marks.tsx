import type { ReactNode } from "react";

/** Points of a starburst, like the price burst on a magazine cover. */
function burstPoints(points: number, outer: number, inner: number): string {
  const out: string[] = [];
  for (let i = 0; i < points * 2; i++) {
    const radius = i % 2 === 0 ? outer : inner;
    const angle = (Math.PI * i) / points - Math.PI / 2;
    out.push(`${(50 + radius * Math.cos(angle)).toFixed(2)},${(50 + radius * Math.sin(angle)).toFixed(2)}`);
  }
  return out.join(" ");
}

const BURST = burstPoints(18, 50, 42);

/** A cover-burst sticker. The word inside is the meaning; the shape only frames it. */
export function Burst({ tone, children, className = "" }: { tone: string; children: ReactNode; className?: string }) {
  return (
    <span className={`burst ${tone} ${className}`}>
      <svg viewBox="0 0 100 100" aria-hidden>
        <polygon points={BURST} />
      </svg>
      <span className="burst-word">{children}</span>
    </span>
  );
}
