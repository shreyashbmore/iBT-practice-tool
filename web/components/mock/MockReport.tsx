import Link from "next/link";
import type { OverallBand } from "@/lib/api";

const ORDER = ["reading", "listening", "writing", "speaking"];
const LABEL: Record<string, string> = { reading: "Reading", listening: "Listening", writing: "Writing", speaking: "Speaking" };

export default function MockReport({ result, responseLinks }: {
  result: OverallBand; responseLinks?: Record<string, string[]>;
}) {
  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-center gap-8">
        <div>
          <div className="text-sm text-slate-500">Estimated overall band</div>
          <div className="text-5xl font-semibold tabular-nums">{result.band.toFixed(1)}</div>
          <div className="text-sm text-slate-600">CEFR {result.cefr} · comparable total ≈ {result.comparable_total} / 120</div>
        </div>
        <p className="max-w-md text-xs text-slate-500">
          Overall = mean of the four section bands, rounded to the nearest 0.5. Section bands are estimated by placing
          your section percentage on the old 0–30 scale and using ETS&apos;s published comparison table
          ({result.version}). This is not an official score.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {ORDER.filter((s) => result.sections[s]).map((s) => {
          const b = result.sections[s];
          return (
            <div key={s} className="card space-y-1">
              <div className="text-sm text-slate-500">{LABEL[s]}</div>
              <div className="text-3xl font-semibold tabular-nums">{b.band.toFixed(1)}</div>
              <div className="text-sm text-slate-600">CEFR {b.cefr}</div>
              <div className="text-xs text-slate-500">
                raw {Number.isInteger(b.raw) ? b.raw : b.raw.toFixed(1)} / {b.max} · {b.percent}% · ≈ {b.old_scale}/30
              </div>
              {responseLinks?.[s]?.length ? (
                <div className="flex flex-wrap gap-x-2 pt-1 text-xs">
                  {responseLinks[s].map((rid, i) => (
                    <Link key={rid} href={`/report/${rid}`} className="text-indigo-700 hover:underline">
                      {responseLinks[s].length > 1 ? `report ${i + 1}` : "detailed report"}
                    </Link>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
