"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type SettingsOut } from "@/lib/api";

export default function SetupStatus() {
  const [s, setS] = useState<SettingsOut | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.getSettings().then(setS).catch((e: Error) => setErr(e.message));
  }, []);

  if (err) return <div className="card border-red-200 bg-red-50 text-sm text-red-800">{err}</div>;
  if (!s) return <div className="card text-sm text-slate-500">Checking setup…</div>;

  const p = s.providers.find((x) => x.id === s.settings.llm.provider);
  const llmReady = p ? !p.needs_key || s.llm_keys[p.id]?.set : false;
  const dgReady = s.deepgram_key.set;
  if (llmReady && dgReady) {
    return (
      <div className="card text-sm text-emerald-800">
        Ready · LLM: <b>{p?.label}</b> / {s.settings.llm.model} · Speech: <b>Deepgram</b>
      </div>
    );
  }
  return (
    <div className="card border-amber-200 bg-amber-50 text-sm text-amber-900">
      Finish setup:{" "}
      {!llmReady && <span>add a key for {p?.label ?? "your LLM"}. </span>}
      {!dgReady && <span>add a Deepgram key (needed for Speaking & Listening). </span>}
      <Link href="/settings" className="font-medium underline">Open settings →</Link>
    </div>
  );
}
