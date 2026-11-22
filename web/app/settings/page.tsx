"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type KeyCheck, type SettingsOut } from "@/lib/api";
import { CheckResult, KeyBadge } from "@/components/Status";

export default function SettingsPage() {
  const [data, setData] = useState<SettingsOut | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // LLM form
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [llmKey, setLlmKey] = useState("");
  const [llmCheck, setLlmCheck] = useState<KeyCheck | null>(null);

  // Deepgram form
  const [dgKey, setDgKey] = useState("");
  const [sttModel, setSttModel] = useState("");
  const [voice, setVoice] = useState("");
  const [dgCheck, setDgCheck] = useState<KeyCheck | null>(null);

  const [samples, setSamples] = useState(3);
  const [busy, setBusy] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const load = async () => {
    try {
      const d = await api.getSettings();
      setData(d);
      setProvider(d.settings.llm.provider);
      setModel(d.settings.llm.model);
      setApiBase(d.settings.llm.api_base ?? "");
      setSttModel(d.settings.speech.stt_model ?? "");
      setVoice(d.settings.speech.tts_voice ?? "");
      setSamples(d.settings.scoring?.samples ?? 3);
      setErr(null);
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const info = useMemo(() => data?.providers.find((p) => p.id === provider), [data, provider]);
  const keyStatus = data?.llm_keys[provider];

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setSaved(null);
    try {
      await fn();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const saveLLM = () =>
    run("llm-save", async () => {
      if (llmKey.trim()) await api.saveKey(provider, llmKey.trim());
      await api.saveSettings({
        llm: { provider, model: model.trim(), api_base: apiBase.trim() || null },
        scoring: { samples },
      });
      setLlmKey("");
      setSaved("LLM settings saved");
      await load();
    });

  const testLLM = () =>
    run("llm-test", async () => {
      setLlmCheck(null);
      setLlmCheck(
        await api.testLLM({
          provider,
          model: model.trim(),
          api_base: apiBase.trim() || null,
          api_key: llmKey.trim() || undefined,
        }),
      );
    });

  const saveDG = () =>
    run("dg-save", async () => {
      if (dgKey.trim()) await api.saveKey("deepgram", dgKey.trim());
      await api.saveSettings({
        speech: { provider: "deepgram", stt_model: sttModel.trim() || null, tts_voice: voice.trim() || null },
      });
      setDgKey("");
      setSaved("Speech settings saved");
      await load();
    });

  const testDG = () =>
    run("dg-test", async () => {
      setDgCheck(null);
      setDgCheck(await api.testDeepgram(dgKey.trim() || undefined));
    });

  const removeKey = (name: string) =>
    run(`rm-${name}`, async () => {
      await api.deleteKey(name);
      await load();
    });

  if (!data) {
    return <p className="text-sm text-slate-500">{err ?? "Loading…"}</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="mt-1 text-sm text-slate-600">
          Keys are stored on this computer only (OS keychain) and are never sent back to the browser.
          Your audio and text go only to the providers you choose here.
        </p>
      </div>
      {err && <div className="card border-red-200 bg-red-50 text-sm text-red-800">{err}</div>}
      {saved && <div className="card border-emerald-200 bg-emerald-50 text-sm text-emerald-800">{saved}</div>}

      {/* LLM */}
      <section className="card space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Language model (scoring & feedback)</h2>
          {keyStatus && <KeyBadge {...keyStatus} />}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="provider">Provider</label>
            <select
              id="provider"
              className="input"
              value={provider}
              onChange={(e) => {
                const p = data.providers.find((x) => x.id === e.target.value);
                setProvider(e.target.value);
                setModel(p?.models[0] ?? "");
                setApiBase(p?.default_api_base ?? "");
                setLlmCheck(null);
              }}
            >
              {data.providers.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="model">Model</label>
            <input id="model" className="input" list="model-suggestions" value={model}
              onChange={(e) => setModel(e.target.value)} placeholder="model id" />
            <datalist id="model-suggestions">
              {info?.models.map((m) => <option key={m} value={m} />)}
            </datalist>
            <p className="mt-1 text-xs text-slate-500">Suggestions only — any model id your provider supports works.</p>
          </div>
          {info?.needs_key && (
            <div className="sm:col-span-2">
              <label className="label" htmlFor="llmkey">API key</label>
              <div className="flex gap-2">
                <input id="llmkey" type="password" autoComplete="off" className="input" value={llmKey}
                  onChange={(e) => setLlmKey(e.target.value)}
                  placeholder={keyStatus?.set ? "Leave blank to keep the saved key" : "Paste your key"} />
                {keyStatus?.set && keyStatus.source !== "env" && (
                  <button className="btn-danger" onClick={() => removeKey(provider)} disabled={!!busy}>Remove</button>
                )}
              </div>
              {info.key_url && (
                <a className="mt-1 inline-block text-xs text-indigo-700 underline" href={info.key_url}
                  target="_blank" rel="noreferrer">Get a {info.label} key</a>
              )}
            </div>
          )}
          <div>
            <label className="label" htmlFor="samples">Scoring passes per response</label>
            <select id="samples" className="input" value={samples} onChange={(e) => setSamples(Number(e.target.value))}>
              <option value={1}>1 · cheapest</option>
              <option value={3}>3 · recommended (median, flags disagreement)</option>
              <option value={5}>5 · most stable</option>
            </select>
            <p className="mt-1 text-xs text-slate-500">More passes = steadier scores, higher cost.</p>
          </div>
          {info?.needs_api_base && (
            <div className="sm:col-span-2">
              <label className="label" htmlFor="apibase">API base URL</label>
              <input id="apibase" className="input" value={apiBase} onChange={(e) => setApiBase(e.target.value)} />
            </div>
          )}
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={testLLM} disabled={!!busy || !model.trim()}>
            {busy === "llm-test" ? "Testing…" : "Test"}
          </button>
          <button className="btn-primary" onClick={saveLLM} disabled={!!busy || !model.trim()}>
            {busy === "llm-save" ? "Saving…" : "Save"}
          </button>
        </div>
        <CheckResult r={llmCheck} />
      </section>

      {/* Deepgram */}
      <section className="card space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Speech (Deepgram)</h2>
          <KeyBadge {...data.deepgram_key} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="label" htmlFor="dgkey">API key</label>
            <div className="flex gap-2">
              <input id="dgkey" type="password" autoComplete="off" className="input" value={dgKey}
                onChange={(e) => setDgKey(e.target.value)}
                placeholder={data.deepgram_key.set ? "Leave blank to keep the saved key" : "Paste your Deepgram key"} />
              {data.deepgram_key.set && data.deepgram_key.source !== "env" && (
                <button className="btn-danger" onClick={() => removeKey("deepgram")} disabled={!!busy}>Remove</button>
              )}
            </div>
            <a className="mt-1 inline-block text-xs text-indigo-700 underline" href="https://console.deepgram.com/"
              target="_blank" rel="noreferrer">Get a Deepgram key</a>
          </div>
          <div>
            <label className="label" htmlFor="stt">Speech-to-text model</label>
            <input id="stt" className="input" value={sttModel} onChange={(e) => setSttModel(e.target.value)}
              placeholder={`default: ${data.defaults.stt_model}`} />
          </div>
          <div>
            <label className="label" htmlFor="voice">Text-to-speech voice</label>
            <input id="voice" className="input" value={voice} onChange={(e) => setVoice(e.target.value)}
              placeholder={`default: ${data.defaults.tts_voice}`} />
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={testDG} disabled={!!busy}>
            {busy === "dg-test" ? "Testing…" : "Test"}
          </button>
          <button className="btn-primary" onClick={saveDG} disabled={!!busy}>
            {busy === "dg-save" ? "Saving…" : "Save"}
          </button>
        </div>
        <CheckResult r={dgCheck} />
      </section>
    </div>
  );
}
