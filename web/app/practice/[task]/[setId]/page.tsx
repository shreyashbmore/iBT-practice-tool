"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { practice, type BuildItem, type DiscussionItem, type EmailItem, type PracticeSet, type SpeakingItem } from "@/lib/api";
import BuildSentenceRunner from "@/components/practice/BuildSentenceRunner";
import WritingRunner from "@/components/practice/WritingRunner";
import SpeakingRunner from "@/components/speaking/SpeakingRunner";
import ObjectivePractice from "@/components/objective/ObjectivePractice";
import { OBJECTIVE_TASKS } from "@/lib/tasks";

export default function PracticeRunner() {
  const { task, setId } = useParams<{ task: string; setId: string }>();
  const [set, setSet] = useState<PracticeSet | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    practice.getSet(setId).then(setSet).catch((e: Error) => setErr(e.message));
  }, [setId]);

  if (err) return <div className="card border-red-200 bg-red-50 text-sm text-red-800">{err}</div>;
  if (!set) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="space-y-4">
      <Link href={`/practice/${task}`} className="text-sm text-slate-500 hover:underline">← {set.title}</Link>
      {set.task === "build-a-sentence" && <BuildSentenceRunner set={set} items={set.items as BuildItem[]} />}
      {(set.task === "write-an-email" || set.task === "academic-discussion") && (
        <WritingRunner set={set} item={set.items[0] as EmailItem | DiscussionItem} />
      )}
      {OBJECTIVE_TASKS.has(set.task) && <ObjectivePractice set={set} />}
      {(set.task === "listen-and-repeat" || set.task === "take-an-interview") && (
        <SpeakingRunner set={set} items={set.items as unknown as SpeakingItem[]} />
      )}
    </div>
  );
}
