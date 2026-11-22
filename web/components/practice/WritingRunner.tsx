"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { practice, type DiscussionItem, type EmailItem, type PracticeSet, type TextOut } from "@/lib/api";
import { useCountdown } from "@/lib/useCountdown";
import Timer from "@/components/Timer";
import StartScreen from "./StartScreen";
import ScorePanel from "@/components/ScorePanel";

const countWords = (t: string) => (t.match(/[A-Za-z]+(?:['’][A-Za-z]+)?/g) ?? []).length;

export function EmailOrDiscussionPrompt({ item }: { item: EmailItem | DiscussionItem }) {
  return item.task === "write-an-email" ? <EmailPrompt item={item} /> : <DiscussionPrompt item={item} />;
}

export default function WritingRunner({ set, item, onDone }: {
  set: PracticeSet; item: EmailItem | DiscussionItem; onDone?: (responseId: string) => void;
}) {
  const [phase, setPhase] = useState<"intro" | "test" | "done">("intro");
  const [text, setText] = useState("");
  const [out, setOut] = useState<TextOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const textRef = useRef(text);
  textRef.current = text;

  const submit = useCallback(
    async (timedOut: boolean) => {
      setSubmitting(true);
      setErr(null);
      try {
        const r = await practice.submitText(set.id, item.id, textRef.current, timer.elapsed(), timedOut);
        timer.stop();
        if (onDone) {
          onDone(r.response_id);
          return;
        }
        setOut(r);
        setPhase("done");
      } catch (e) {
        setErr((e as Error).message);
      } finally {
        setSubmitting(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [set.id, item.id, onDone],
  );
  const timer = useCountdown(set.time_limit_s, () => submit(true));

  // warn before leaving mid-task
  useEffect(() => {
    if (phase !== "test") return;
    const h = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [phase]);

  if (phase === "intro") {
    return (
      <StartScreen title={set.title} directions={set.directions} minutes={Math.round(set.time_limit_s / 60)}
        onStart={() => { timer.start(); setPhase("test"); }} />
    );
  }

  const words = countWords(text);
  const isEmail = item.task === "write-an-email";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="font-semibold">{set.title}</h1>
        {phase === "test" && <Timer remaining={timer.remaining} total={set.time_limit_s} />}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card space-y-3 text-[15px] leading-relaxed">
          {isEmail ? <EmailPrompt item={item as EmailItem} /> : <DiscussionPrompt item={item as DiscussionItem} />}
        </div>

        <div className="card flex flex-col gap-2">
          {isEmail && (
            <div className="text-sm text-slate-600">
              <div><b>To:</b> {(item as EmailItem).recipient}</div>
              {(item as EmailItem).subject && <div><b>Subject:</b> {(item as EmailItem).subject}</div>}
            </div>
          )}
          <textarea
            className="input min-h-80 flex-1 font-[inherit] leading-relaxed"
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={phase !== "test"}
            spellCheck={false}
            autoCorrect="off"
            autoCapitalize="off"
            placeholder={isEmail ? "Write your email here…" : "Write your response here…"}
          />
          <div className="flex items-center justify-between text-sm">
            <span className={!isEmail && words < 100 ? "text-amber-700" : "text-slate-500"}>
              Word count: {words}{!isEmail && " (aim for 100+)"}
            </span>
            {phase === "test" && (
              <button className="btn-primary" onClick={() => submit(false)} disabled={submitting || !text.trim()}>
                {submitting ? "Submitting…" : "Submit"}
              </button>
            )}
          </div>
          {err && <p className="text-sm text-red-700">{err}</p>}
        </div>
      </div>

      {phase === "done" && out && (
        <>
          <ScorePanel responseId={out.response_id} text={text} />
          <SubmittedPanel out={out} isEmail={isEmail} />
        </>
      )}
    </div>
  );
}

function EmailPrompt({ item }: { item: EmailItem }) {
  return (
    <>
      <p>{item.scenario}</p>
      <p className="font-medium">Write an email to {item.recipient}. In your email, do the following:</p>
      <ul className="list-disc space-y-1 pl-5">
        {item.points.map((p) => <li key={p}>{p}</li>)}
      </ul>
    </>
  );
}

function DiscussionPrompt({ item }: { item: DiscussionItem }) {
  return (
    <>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{item.course}</div>
      <div className="rounded-lg bg-indigo-50 p-3">
        <div className="text-sm font-semibold text-indigo-900">{item.professor.name}</div>
        <p>{item.professor.text}</p>
      </div>
      {item.students.map((s) => (
        <div key={s.name} className="rounded-lg bg-slate-50 p-3">
          <div className="text-sm font-semibold">{s.name}</div>
          <p>{s.text}</p>
        </div>
      ))}
    </>
  );
}

function SubmittedPanel({ out, isEmail }: { out: TextOut; isEmail: boolean }) {
  const f = out.features;
  const stats: [string, string | number][] = [
    ["Words", f.word_count],
    ["Sentences", f.sentence_count],
    ["Avg. sentence length", `${f.mean_sentence_len} words`],
    ["Sentence length variety (SD)", f.sentence_len_sd],
    ["Vocabulary variety (TTR)", f.type_token_ratio],
    ["Copied from prompt", `${Math.round(f.stimulus_overlap * 100)}%`],
  ];
  if (isEmail) {
    stats.push(["Greeting", f.has_greeting ? "yes" : "missing"], ["Closing", f.has_closing ? "yes" : "missing"]);
  }
  return (
    <details className="card space-y-3">
      <summary className="flex cursor-pointer items-center justify-between">
        <span className="font-semibold">Measured features</span>
        <button className="btn-ghost" onClick={() => window.location.reload()}>Practise again</button>
      </summary>
      <p className="mt-2 text-sm text-slate-600">These measurements are given to the scorer as facts.</p>
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        {stats.map(([k, v]) => (
          <div key={k} className="rounded-lg border border-slate-200 p-3">
            <dt className="text-xs text-slate-500">{k}</dt>
            <dd className="font-medium">{v}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
