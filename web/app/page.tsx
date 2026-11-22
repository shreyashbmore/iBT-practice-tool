import Link from "next/link";
import { SECTIONS } from "@/lib/tasks";
import SetupStatus from "@/components/SetupStatus";
import SectionTests from "@/components/SectionTests";

export default function Home() {
  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-2xl font-semibold">TOEFL iBT practice — 2026 format</h1>
        <p className="mt-1 text-slate-600">
          Section bands on the 1–6 scale (with CEFR and a comparable 0–120), scored against the official task rubrics.
        </p>
      </section>
      <SetupStatus />
      <SectionTests />
      <div className="grid gap-4 sm:grid-cols-2">
        {SECTIONS.map((s) => (
          <div key={s.id} className="card">
            <div className="flex items-baseline justify-between">
              <h2 className="font-semibold">{s.name}</h2>
              <span className="text-xs text-slate-500">{s.time}</span>
            </div>
            <ul className="mt-3 space-y-2">
              {s.tasks.map((t) => (
                <li key={t.id} className="flex items-center justify-between text-sm">
                  <span>{t.name}</span>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                    {t.ready ? <Link href={`/practice/${t.id}`}>Practice</Link> : "coming soon"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
