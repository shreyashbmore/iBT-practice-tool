"use client";

import { useState } from "react";

/** Single-series line chart: 2px line, end dot with surface ring, hairline grid, hover tooltip, table view. */
export type Pt = { x: string; y: number; label?: string };

const SERIES = "#2a78d6";
const SURFACE = "#ffffff";

export default function LineChart({ points, yMin, yMax, yTicks, format = (v) => String(v), height = 160, title }: {
  points: Pt[]; yMin: number; yMax: number; yTicks: number[]; format?: (v: number) => string; height?: number;
  title: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 560, H = height, L = 36, R = 44, T = 10, B = 22;
  const iw = W - L - R, ih = H - T - B;
  const x = (i: number) => L + (points.length <= 1 ? iw / 2 : (i / (points.length - 1)) * iw);
  const y = (v: number) => T + ih - ((v - yMin) / (yMax - yMin)) * ih;
  const d = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.y).toFixed(1)}`).join(" ");
  const last = points[points.length - 1];

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    let best = 0;
    points.forEach((_, i) => { if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i; });
    setHover(points.length ? best : null);
  };

  return (
    <figure className="space-y-1">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={title}
        onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="#e7e6e2" strokeWidth={1} />
            <text x={L - 6} y={y(t) + 4} textAnchor="end" fontSize={11} fill="#52514e">{format(t)}</text>
          </g>
        ))}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={T} y2={T + ih} stroke="#c9c8c2" strokeWidth={1} />}
        {points.length > 1 && <path d={d} fill="none" stroke={SERIES} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />}
        {points.map((p, i) => (i === points.length - 1 || i === hover) && (
          <circle key={i} cx={x(i)} cy={y(p.y)} r={4} fill={SERIES} stroke={SURFACE} strokeWidth={2} />
        ))}
        {last && <text x={x(points.length - 1) + 8} y={y(last.y) + 4} fontSize={12} fill="#0b0b0b" fontWeight={600}>{format(last.y)}</text>}
        {hover !== null && (() => {
          const p = points[hover];
          const tx = Math.min(Math.max(x(hover) - 60, L), W - R - 120);
          return (
            <g pointerEvents="none">
              <rect x={tx} y={T} width={120} height={36} rx={6} fill="#0b0b0b" opacity={0.88} />
              <text x={tx + 8} y={T + 15} fontSize={11} fill="#f0efec">{p.x}</text>
              <text x={tx + 8} y={T + 29} fontSize={12} fill="#ffffff" fontWeight={600}>{p.label ?? format(p.y)}</text>
            </g>
          );
        })()}
      </svg>
      <details className="text-xs text-slate-500">
        <summary className="cursor-pointer">Table view</summary>
        <table className="mt-1 w-full text-left">
          <tbody>{points.map((p, i) => <tr key={i}><td className="pr-4">{p.x}</td><td>{p.label ?? format(p.y)}</td></tr>)}</tbody>
        </table>
      </details>
    </figure>
  );
}
