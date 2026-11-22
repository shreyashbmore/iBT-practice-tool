export default function Timer({ remaining, total }: { remaining: number; total: number }) {
  const s = Math.ceil(remaining);
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  const low = remaining <= Math.min(60, total * 0.15);
  return (
    <div
      className={`rounded-lg border px-3 py-1.5 font-mono text-sm tabular-nums ${
        low ? "border-red-300 bg-red-50 text-red-700" : "border-slate-300 bg-white text-slate-700"
      }`}
      aria-live="polite"
      title="Time remaining"
    >
      ⏱ {mm}:{ss}
    </div>
  );
}
