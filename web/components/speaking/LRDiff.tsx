import type { AlignedToken } from "@/lib/api";

const LEGEND: [string, string][] = [
  ["text-slate-900", "said correctly"],
  ["text-red-600 line-through", "missing"],
  ["text-amber-700 underline decoration-dotted", "changed"],
  ["text-violet-700 underline", "moved"],
  ["text-slate-400", "+ extra"],
];

export default function LRDiff({ tokens }: { tokens: AlignedToken[] }) {
  return (
    <div className="space-y-2">
      <p className="leading-8">
        {tokens.filter((t) => t.op !== "repeat").map((t, i) => {
          const key = `${i}-${t.op}`;
          const lowConf = t.op === "match" && t.content && (t.confidence ?? 1) < 0.5;
          switch (t.op) {
            case "match":
              return (
                <span key={key} title={lowConf ? "unclear pronunciation" : undefined}
                  className={lowConf ? "underline decoration-red-400 decoration-wavy" : ""}>{t.expected} </span>
              );
            case "del":
              return <span key={key} className={`line-through ${t.content ? "text-red-600" : "text-red-400"}`}>{t.expected} </span>;
            case "sub":
            case "inflect":
              return (
                <span key={key} className="text-amber-700 underline decoration-dotted"
                  title={`expected “${t.expected}”`}>{t.heard}<sup className="text-[10px]"> ({t.expected})</sup> </span>
              );
            case "moved":
              return <span key={key} className="text-violet-700 underline" title="said in a different position">{t.expected} </span>;
            case "ins":
              return <span key={key} className="text-slate-400">+{t.heard} </span>;
            default:
              return null;
          }
        })}
      </p>
      <p className="flex flex-wrap gap-3 text-xs text-slate-500">
        {LEGEND.map(([cls, label]) => <span key={label} className={cls}>{label}</span>)}
      </p>
    </div>
  );
}
