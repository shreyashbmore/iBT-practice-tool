"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  practice, scoring, type BuildItem, type BuildResult, type DiscussionItem, type EmailItem, type PracticeSet,
  type ResponseDetail, type WritingScore,
} from "@/lib/api";
import { OBJECTIVE_TASKS, taskName } from "@/lib/tasks";
import ObjectiveResults from "@/components/objective/ObjectiveResults";
import MockReport from "@/components/mock/MockReport";
import type { OverallBand } from "@/lib/api";
import type { ObjectiveResult, StageResult } from "@/lib/api";
import ScorePanel from "@/components/ScorePanel";
import { BuildResults } from "@/components/practice/BuildSentenceRunner";
import { EmailOrDiscussionPrompt } from "@/components/practice/WritingRunner";
import SpeakingResultCard from "@/components/speaking/SpeakingResultCard";
import type { ListenRepeatResult, SpeakingOut, SpeechFeatures, Transcript } from "@/lib/api";

export default function Report() {
  const { id } = useParams<{ id: string }>();
  const [r, setR] = useState<ResponseDetail | null>(null);
  const [set, setSet] = useState<PracticeSet | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const resp = await scoring.get(id);
        setR(resp);
        if (resp.task.endsWith("-test") || resp.task === ("mock-test" as string)) {
          setSet({ id: resp.set_id, title: resp.set_id, items: [] } as unknown as PracticeSet);
        } else {
          setSet(await practice.getSet(resp.set_id));
        }
      } catch (e) {
        setErr((e as Error).message);
      }
    })();
  }, [id]);

  if (err) return <div className="card border-red-200 bg-red-50 text-sm text-red-800">{err}</div>;
  if (!r || !set) return <p className="text-sm text-slate-500">Loading…</p>;

  const when = new Date(r.created_at).toLocaleString();
  const header = (
    <div>
      <Link href="/history" className="text-sm text-slate-500 hover:underline">← History</Link>
      <h1 className="mt-1 text-2xl font-semibold">{taskName(r.task)}</h1>
      <p className="text-sm text-slate-500">
        {set.title} · {when}
        {r.time_spent_s != null && ` · ${Math.round(r.time_spent_s)} s`}
        {r.timed_out && " · timed out"}
      </p>
    </div>
  );

  if ((r.task as string) === "mock-test") {
    return (
      <div className="space-y-4">
        {header}
        <MockReport result={r.score_json as unknown as OverallBand} />
      </div>
    );
  }

  if (r.task.endsWith("-test")) {
    const sj = r.score_json as unknown as { route: string; stages: StageResult[]; band?: { band: number; cefr: string } } | null;
    return (
      <div className="space-y-4">
        {header}
        <div className="card text-lg font-semibold">
          {r.score} / {r.max_score} · module 2: {sj?.route}
          {sj?.band && ` · estimated band ${sj.band.band.toFixed(1)} (${sj.band.cefr})`}
        </div>
        {sj?.stages.map((st) => (
          <div key={st.stage} className="space-y-2">
            <h2 className="font-semibold">{st.stage === "router" ? "Module 1" : `Module 2 (${st.stage})`} — {st.score} / {st.max_score}</h2>
            <ObjectiveResults results={st.sets} />
          </div>
        ))}
      </div>
    );
  }

  if (OBJECTIVE_TASKS.has(r.task)) {
    return (
      <div className="space-y-4">
        {header}
        <div className="card text-lg font-semibold">{r.score} / {r.max_score}</div>
        <ObjectiveResults results={[r.score_json as unknown as ObjectiveResult]} titles={{ [r.set_id]: set.title }} />
      </div>
    );
  }

  if (r.task === "build-a-sentence") {
    const results = (r.score_json as { results: BuildResult[] } | null)?.results ?? [];
    return (
      <div className="space-y-4">
        {header}
        <BuildResults items={set.items as BuildItem[]}
          result={{ response_id: r.id, score: r.score ?? 0, max_score: r.max_score ?? results.length, results }} />
      </div>
    );
  }

  if (r.task === "listen-and-repeat" || r.task === "take-an-interview") {
    const p = r.payload as { prompt_text?: string; transcript?: Transcript; features?: SpeechFeatures };
    const isLR = r.task === "listen-and-repeat";
    const out: SpeakingOut = {
      response_id: r.id, task: r.task, prompt_text: p.prompt_text ?? "",
      transcript: p.transcript ?? null, features: p.features ?? null,
      listen_repeat: isLR ? (r.score_json as ListenRepeatResult | null) : null,
      error: p.transcript ? null : "This recording hasn't been transcribed yet.",
    };
    return (
      <div className="space-y-4">
        {header}
        <SpeakingResultCard out={out} autoScore={false}
          initialScore={isLR ? null : (r.score_json as WritingScore | null)} />
      </div>
    );
  }

  const item = set.items.find((i) => i.id === r.item_id) as EmailItem | DiscussionItem | undefined;
  return (
    <div className="space-y-4">
      {header}
      {item && (
        <details className="card">
          <summary className="cursor-pointer font-medium">Prompt</summary>
          <div className="mt-3 space-y-3 text-[15px] leading-relaxed"><EmailOrDiscussionPrompt item={item} /></div>
        </details>
      )}
      <ScorePanel responseId={r.id} text={r.text ?? ""} initial={r.score_json as WritingScore | null} auto={false} />
    </div>
  );
}
