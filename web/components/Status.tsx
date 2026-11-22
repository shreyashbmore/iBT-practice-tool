import type { KeyCheck } from "@/lib/api";

export function CheckResult({ r }: { r: KeyCheck | null }) {
  if (!r) return null;
  return (
    <p className={`mt-2 text-sm ${r.ok ? "text-emerald-700" : "text-red-700"}`}>
      {r.ok ? "✓ " : "✗ "}
      {r.message}
      {r.latency_ms != null && <span className="text-slate-500"> · {r.latency_ms} ms</span>}
    </p>
  );
}

export function KeyBadge({ set, masked, source }: { set: boolean; masked: string | null; source: string | null }) {
  return set ? (
    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">
      saved {masked} · {source}
    </span>
  ) : (
    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">no key</span>
  );
}
