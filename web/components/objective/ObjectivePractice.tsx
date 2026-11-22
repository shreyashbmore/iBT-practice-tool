"use client";

import { useState } from "react";
import { objective, type ObjectiveResult, type PracticeSet } from "@/lib/api";
import StartScreen from "@/components/practice/StartScreen";
import ObjectiveModule from "./ObjectiveModule";
import ObjectiveResults from "./ObjectiveResults";

export default function ObjectivePractice({ set }: { set: PracticeSet }) {
  const [phase, setPhase] = useState<"intro" | "test" | "done">("intro");
  const [result, setResult] = useState<ObjectiveResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  if (phase === "intro") {
    return <StartScreen title={set.title} directions={set.directions} minutes={Math.round(set.time_limit_s / 60)}
      onStart={() => setPhase("test")} />;
  }
  if (phase === "test") {
    return (
      <>
        {err && <p className="text-sm text-red-700">{err}</p>}
        <ObjectiveModule sets={[set]} timeLimit={set.time_limit_s} onSubmit={async (answers, elapsed, timedOut) => {
          try {
            setResult(await objective.submit(set.id, answers[set.id] ?? {}, elapsed, timedOut));
            setPhase("done");
          } catch (e) {
            setErr((e as Error).message);
          }
        }} />
      </>
    );
  }
  return (
    <div className="space-y-4">
      <div className="card flex items-center justify-between">
        <div>
          <div className="text-sm text-slate-500">{set.title}</div>
          <div className="text-3xl font-semibold">{result?.score}<span className="text-lg text-slate-400"> / {result?.max_score}</span></div>
        </div>
        <button className="btn-ghost" onClick={() => window.location.reload()}>Practise again</button>
      </div>
      {result && <ObjectiveResults results={[result]} titles={{ [set.id]: "Answers" }} />}
    </div>
  );
}
