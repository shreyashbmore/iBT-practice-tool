"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import {
  mock, practice, type BuildItem, type DiscussionItem, type EmailItem, type MockAttempt, type MockPlan,
  type OverallBand, type PracticeSet, type SpeakingItem,
} from "@/lib/api";
import { AdaptiveSection } from "@/components/test/AdaptiveSection";
import BuildSentenceRunner from "@/components/practice/BuildSentenceRunner";
import WritingRunner from "@/components/practice/WritingRunner";
import SpeakingRunner from "@/components/speaking/SpeakingRunner";
import MockReport from "@/components/mock/MockReport";

const SECTION_LABEL: Record<string, string> = { reading: "Reading", listening: "Listening", writing: "Writing", speaking: "Speaking" };

function Steps({ sections, current }: { sections: string[]; current: string | null }) {
  const idx = current ? sections.indexOf(current) : sections.length;
  return (
    <ol className="flex gap-2 text-sm">
      {sections.map((s, i) => (
        <li key={s} className={`rounded-full border px-3 py-1 ${i < idx ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : i === idx ? "border-indigo-300 bg-indigo-50 font-medium text-indigo-800" : "border-slate-200 text-slate-500"}`}>
          {i < idx ? "✓ " : ""}{SECTION_LABEL[s]}
        </li>
      ))}
    </ol>
  );
}

/** Runs several sets one after another and reports all response ids at the end. */
function MultiPart({ parts, render, onDone }: {
  parts: string[];
  render: (set: PracticeSet, done: (ids: string[]) => void) => React.ReactNode;
  onDone: (ids: string[]) => void;
}) {
  const [i, setI] = useState(0);
  const [ids, setIds] = useState<string[]>([]);
  const [set, setSet] = useState<PracticeSet | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setSet(null);
    practice.getSet(parts[i]).then(setSet).catch((e: Error) => setErr(e.message));
  }, [i, parts]);
  if (err) return <p className="text-sm text-red-700">{err}</p>;
  if (!set) return <p className="text-sm text-slate-500">Loading…</p>;
  return (
    <div key={set.id}>
      {render(set, (newIds) => {
        const all = [...ids, ...newIds];
        if (i + 1 < parts.length) {
          setIds(all);
          setI(i + 1);
        } else {
          onDone(all);
        }
      })}
    </div>
  );
}

function MockRunner() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const aid = search.get("a");
  const [plan, setPlan] = useState<MockPlan | null>(null);
  const [attempt, setAttempt] = useState<MockAttempt | null>(null);
  const [result, setResult] = useState<OverallBand | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      if (aid) {
        const a = await mock.get(aid);
        setAttempt(a);
        setPlan(a.plan);
        if (a.result) setResult(a.result);
      } else {
        setPlan((await mock.list()).find((m) => m.id === id) ?? null);
      }
    } catch (e) {
      setErr((e as Error).message);
    }
  }, [aid, id]);
  useEffect(() => {
    load();
  }, [load]);

  const start = async () => {
    const r = await mock.start(id);
    router.replace(`/mock/${id}?a=${r.attempt_id}`);
  };

  const record = async (section: string, ids: string[]) => {
    if (!attempt) return;
    setErr(null);
    try {
      await mock.record(attempt.id, section, ids);
      setAttempt(await mock.get(attempt.id));
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const finish = async () => {
    if (!attempt) return;
    setBusy(true);
    setErr(null);
    try {
      setResult(await mock.finish(attempt.id));
      setAttempt(await mock.get(attempt.id));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!plan) return <p className="text-sm text-slate-500">{err ?? "Loading…"}</p>;

  if (!attempt) {
    return (
      <div className="card space-y-4">
        <h1 className="text-2xl font-semibold">{plan.title}</h1>
        <p className="text-slate-700">{plan.description}</p>
        <Steps sections={plan.sections} current={plan.sections[0]} />
        <ul className="list-disc pl-5 text-sm text-slate-600">
          <li>Reading and Listening adapt: module 1 decides whether module 2 is easier or harder.</li>
          <li>Writing and Speaking are scored by your LLM at the end, against the 2026 rubrics.</li>
          <li>Your progress is saved after each section; you can reload this page and continue.</li>
        </ul>
        <button className="btn-primary" onClick={start}>Start the test</button>
      </div>
    );
  }

  const next = attempt.next_section;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold">{plan.title}</h1>
        <Steps sections={plan.sections} current={result ? null : next} />
      </div>
      {err && <div className="card border-red-200 bg-red-50 text-sm text-red-800">{err}</div>}

      {next === "reading" && <AdaptiveSection key="r" formId={plan.reading} onDone={(rid) => record("reading", [rid])} />}
      {next === "listening" && <AdaptiveSection key="l" formId={plan.listening} onDone={(rid) => record("listening", [rid])} />}
      {next === "writing" && (
        <MultiPart parts={[plan.writing.build_sentence, plan.writing.email, plan.writing.discussion]}
          onDone={(ids) => record("writing", ids)}
          render={(set, done) => set.task === "build-a-sentence"
            ? <BuildSentenceRunner set={set} items={set.items as BuildItem[]} onDone={(rid) => done([rid])} />
            : <WritingRunner set={set} item={set.items[0] as EmailItem | DiscussionItem} onDone={(rid) => done([rid])} />} />
      )}
      {next === "speaking" && (
        <MultiPart parts={[plan.speaking.listen_repeat, plan.speaking.interview]} onDone={(ids) => record("speaking", ids)}
          render={(set, done) => <SpeakingRunner set={set} items={set.items as unknown as SpeakingItem[]} onDone={done} />} />
      )}

      {next === null && !result && (
        <div className="card space-y-3">
          <h2 className="text-xl font-semibold">All sections complete</h2>
          <p className="text-slate-700">
            Scoring your Writing and Speaking responses with your LLM, then calculating section and overall bands.
            This can take a minute or two.
          </p>
          <button className="btn-primary" onClick={finish} disabled={busy}>{busy ? "Scoring…" : "Calculate my scores"}</button>
        </div>
      )}
      {result && (
        <>
          <MockReport result={result}
            responseLinks={Object.fromEntries(Object.entries(attempt.sections).map(([s, v]) => [s, v.response_ids]))} />
          <Link href="/progress" className="btn-ghost">See your progress →</Link>
        </>
      )}
    </div>
  );
}

export default function MockPage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Loading…</p>}>
      <MockRunner />
    </Suspense>
  );
}
