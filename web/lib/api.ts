export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(`Cannot reach the API at ${API_URL}. Is it running? (make api)`, 0);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {}
    throw new ApiError(detail, res.status);
  }
  const ct = res.headers.get("content-type") ?? "";
  return (ct.includes("application/json") ? res.json() : res.blob()) as Promise<T>;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

// ---- types (mirror api/app) ----
export type ProviderInfo = {
  id: string;
  label: string;
  needs_key: boolean;
  needs_api_base: boolean;
  default_api_base: string | null;
  key_url: string | null;
  models: string[];
};
export type KeyStatus = { set: boolean; masked: string | null; source: string | null };
export type LLMPrefs = { provider: string; model: string; api_base: string | null };
export type SpeechPrefs = { provider: "deepgram"; stt_model: string | null; tts_voice: string | null };
export type ScoringPrefs = { samples: number };
export type UserSettings = { llm: LLMPrefs; speech: SpeechPrefs; scoring: ScoringPrefs };
export type SettingsOut = {
  settings: UserSettings;
  providers: ProviderInfo[];
  llm_keys: Record<string, KeyStatus>;
  deepgram_key: KeyStatus;
  defaults: { stt_model: string; tts_voice: string };
};
export type KeyCheck = { ok: boolean; message: string; latency_ms: number | null };
export type Word = { word: string; punctuated: string | null; start: number; end: number; confidence: number };
export type SpeechFeatures = {
  word_count: number;
  speaking_time_s: number;
  wpm: number;
  articulation_rate_wpm: number;
  pauses_over_0_5s: number;
  pauses_over_1s: number;
  mean_pause_s: number;
  longest_pause_s: number;
  filler_count: number;
  fillers_per_min: number;
  mean_confidence: number;
  low_confidence_words: string[];
};
export type TranscribeOut = {
  transcript: { text: string; words: Word[]; duration_s: number | null; model: string | null };
  features: SpeechFeatures;
};

export const api = {
  getSettings: () => request<SettingsOut>("/api/settings"),
  saveSettings: (body: Partial<UserSettings>) => request<UserSettings>("/api/settings", json("PUT", body)),
  saveKey: (name: string, value: string) => request<KeyStatus>(`/api/keys/${name}`, json("PUT", { value })),
  deleteKey: (name: string) => request<KeyStatus>(`/api/keys/${name}`, json("DELETE")),
  testLLM: (body: Partial<LLMPrefs> & { api_key?: string }) =>
    request<KeyCheck>("/api/keys/test/llm", json("POST", body)),
  testDeepgram: (api_key?: string) => request<KeyCheck>("/api/keys/test/deepgram", json("POST", { api_key })),
  transcribe: (audio: Blob, verbatim = false) => {
    const fd = new FormData();
    fd.append("file", audio, "recording.webm");
    fd.append("verbatim", String(verbatim));
    return request<TranscribeOut>("/api/speech/transcribe", { method: "POST", body: fd });
  },
  tts: (text: string, voice?: string) => request<Blob>("/api/speech/tts", json("POST", { text, voice })),
};

// ---- practice ----
export type ObjectiveTask =
  | "complete-the-words" | "read-daily-life" | "read-academic-passage"
  | "listen-choose-response" | "listen-conversation" | "listen-announcement" | "listen-academic-talk";
export type TaskId =
  | "build-a-sentence" | "write-an-email" | "academic-discussion" | "listen-and-repeat" | "take-an-interview"
  | ObjectiveTask;
export type SetSummary = {
  id: string;
  task: TaskId;
  title: string;
  section: string;
  time_limit_s: number;
  n_items: number;
};
export type BuildItem = {
  id: string;
  task: "build-a-sentence";
  speaker: string;
  context: string;
  template: string;
  chunks: string[];
  slots: number;
};
export type EmailItem = {
  id: string;
  task: "write-an-email";
  scenario: string;
  recipient: string;
  subject: string | null;
  points: string[];
};
export type Post = { name: string; text: string };
export type DiscussionItem = {
  id: string;
  task: "academic-discussion";
  course: string;
  professor: Post;
  students: Post[];
};
export type QuestionPub = { id: string; prompt: string; options: string[] };
export type CWSegment = { type: "text"; text: string } | { type: "gap"; id: string; prefix: string; length: number };
export type CWItem = { id: string; task: "complete-the-words"; title: string | null; segments: CWSegment[] };
export type ReadingItemPub = {
  id: string; task: "read-daily-life" | "read-academic-passage"; title: string | null; genre: string | null;
  text: string; questions: QuestionPub[];
};
export type ListeningItemPub = {
  id: string; task: "listen-choose-response" | "listen-conversation" | "listen-announcement" | "listen-academic-talk";
  context: string | null; questions: QuestionPub[];
};
export type ObjectiveItem = CWItem | ReadingItemPub | ListeningItemPub;
export type PracticeSet = SetSummary & {
  directions: string;
  scene: string | null;
  items: (BuildItem | EmailItem | DiscussionItem | ObjectiveItem)[];
};
export type BuildResult = {
  item_id: string;
  correct: boolean;
  submitted: string[];
  your_sentence: string;
  correct_sentence: string;
  explanation: string | null;
};
export type BuildOut = { response_id: string; score: number; max_score: number; results: BuildResult[] };
export type TextFeatures = {
  word_count: number;
  sentence_count: number;
  paragraph_count: number;
  mean_sentence_len: number;
  sentence_len_sd: number;
  type_token_ratio: number;
  long_word_ratio: number;
  stimulus_overlap: number;
  has_greeting: boolean;
  has_closing: boolean;
};
export type TextOut = { response_id: string; features: TextFeatures; scored: boolean };
export type SavedResponse = {
  id: string;
  created_at: string;
  set_id: string;
  item_id: string | null;
  task: TaskId;
  section: string;
  text: string | null;
  time_spent_s: number | null;
  timed_out: boolean;
  score: number | null;
  max_score: number | null;
};

export const practice = {
  listSets: (task?: string) => request<SetSummary[]>(`/api/sets${task ? `?task=${encodeURIComponent(task)}` : ""}`),
  getSet: (id: string) => request<PracticeSet>(`/api/sets/${encodeURIComponent(id)}`),
  submitBuild: (setId: string, answers: Record<string, string[]>, time_spent_s: number, timed_out: boolean) =>
    request<BuildOut>(`/api/sets/${setId}/build-a-sentence/submit`, json("POST", { answers, time_spent_s, timed_out })),
  submitText: (setId: string, item_id: string, text: string, time_spent_s: number, timed_out: boolean) =>
    request<TextOut>(`/api/sets/${setId}/text/submit`, json("POST", { item_id, text, time_spent_s, timed_out })),
  responses: (task?: string) =>
    request<SavedResponse[]>(`/api/responses${task ? `?task=${encodeURIComponent(task)}` : ""}`),
};

// ---- rubric scoring ----
export type Level = "strong" | "adequate" | "limited" | "weak";
export type DimensionResult = {
  id: string;
  name: string;
  level: Level;
  comment: string;
  evidence: string[];
  unverified: string[];
};
export type ErrorNote = { quote: string; correction: string; type: string; explanation: string | null };
export type Usage = { prompt_tokens: number; completion_tokens: number; cost_usd: number | null };
export type WritingScore = {
  score: number;
  max_score: number;
  label: string;
  samples: number[];
  confidence: "high" | "low";
  guard: string | null;
  dimensions: DimensionResult[];
  rationale: string;
  errors: ErrorNote[];
  next_steps: string[];
  improved_version: string | null;
  provider: string | null;
  model: string | null;
  rubric_version: string;
  prompt_version: string;
  usage: Usage;
  latency_ms: number;
};
export type ResponseDetail = SavedResponse & {
  payload: Record<string, unknown>;
  score_json: (WritingScore | { results: BuildResult[] }) | null;
};

export const scoring = {
  score: (rid: string) => request<WritingScore>(`/api/responses/${rid}/score`, json("POST")),
  get: (rid: string) => request<ResponseDetail>(`/api/responses/${rid}`),
};

// ---- speaking ----
export type SpeakingItem = { id: string; task: "listen-and-repeat" | "take-an-interview"; response_time_s: number };
export type AlignedToken = {
  op: "match" | "inflect" | "sub" | "del" | "ins" | "moved" | "repeat";
  expected: string | null;
  heard: string | null;
  content: boolean;
  confidence: number | null;
};
export type ListenRepeatResult = {
  score: number;
  max_score: number;
  target: string;
  transcript: string;
  tokens: AlignedToken[];
  stats: Record<string, number | boolean>;
  reasons: string[];
};
export type Transcript = TranscribeOut["transcript"];
export type SpeakingOut = {
  response_id: string;
  task: "listen-and-repeat" | "take-an-interview";
  prompt_text: string;
  transcript: Transcript | null;
  features: SpeechFeatures | null;
  listen_repeat: ListenRepeatResult | null;
  error: string | null;
};

export const speaking = {
  itemAudio: (setId: string, itemId: string) => request<Blob>(`/api/sets/${setId}/items/${itemId}/audio`),
  submit: (setId: string, itemId: string, audio: Blob, attemptId: string, timeSpent: number) => {
    const fd = new FormData();
    const ext = audio.type.includes("mp4") ? "m4a" : audio.type.includes("ogg") ? "ogg" : "webm";
    fd.append("file", audio, `answer.${ext}`);
    fd.append("item_id", itemId);
    fd.append("attempt_id", attemptId);
    fd.append("time_spent_s", String(timeSpent));
    return request<SpeakingOut>(`/api/sets/${setId}/speaking/submit`, { method: "POST", body: fd });
  },
  process: (rid: string) => request<SpeakingOut>(`/api/responses/${rid}/process`, json("POST")),
  audioUrl: (rid: string) => `${API_URL}/api/responses/${rid}/audio`,
};

// ---- reading & listening ----
export type Answers = Record<string, Record<string, number | string | null>>;          // item → q/gap → answer
export type SetAnswers = Record<string, Answers>;                                       // set → item → …
export type QuestionResult = {
  id: string; correct: boolean; chosen: number | string | null; answer: number | string;
  prompt: string | null; options: string[] | null; explanation: string | null;
};
export type ItemResult = {
  item_id: string; task: string; score: number; max_score: number; questions: QuestionResult[];
  transcript: { speaker: string; voice: string; text: string }[] | null; full_text: string | null;
};
export type ObjectiveResult = { set_id: string; score: number; max_score: number; items: ItemResult[] };
export type Module = { stage: "router" | "lower" | "upper"; time_limit_s: number; sets: PracticeSet[] };
export type FormSummary = { id: string; section: string; title: string; router_questions: number; est_minutes: number };
export type StageResult = { stage: string; score: number; max_score: number; sets: ObjectiveResult[] };
export type SectionBand = {
  section: string; raw: number; max: number; percent: number; old_scale: number; band: number; cefr: string;
};
export type OverallBand = {
  band: number; cefr: string; comparable_total: number; sections: Record<string, SectionBand>;
  version: string; estimate: boolean;
};
export type FinalResult = {
  response_id: string; route: "lower" | "upper"; score: number; max_score: number; percent: number;
  stages: StageResult[]; band: SectionBand | null;
};

export const objective = {
  submit: (setId: string, answers: Answers, time_spent_s: number, timed_out: boolean) =>
    request<ObjectiveResult & { response_id: string }>(`/api/sets/${setId}/objective/submit`,
      json("POST", { answers, time_spent_s, timed_out })),
};

export const forms = {
  list: () => request<FormSummary[]>("/api/forms"),
  start: (id: string) =>
    request<{ attempt_id: string; form: { id: string; title: string; section: string; directions: string }; module: Module }>(
      `/api/forms/${id}/start`, json("POST")),
  submit: (id: string, aid: string, stage: string, answers: SetAnswers, time_spent_s: number) =>
    request<{ stage_result?: { stage: string; score: number; max_score: number }; next?: Module; final?: FinalResult }>(
      `/api/forms/${id}/attempts/${aid}/submit`, json("POST", { stage, answers, time_spent_s })),
};

// ---- content generation & review ----
export type DraftReview = {
  status: string; generated_at: string; model: string | null; cefr: string; topic: string | null;
  qa: { questions_checked: number; solver_agreed: number; mismatches: string[]; warnings: string[] };
  usage: Usage;
};
export type DraftSummary = SetSummary & { review: DraftReview | null };
export type GenTask = { task: string; label: string; section: string; count: number; guidance: string };

export const drafts = {
  tasks: () => request<GenTask[]>("/api/drafts/tasks"),
  list: () => request<DraftSummary[]>("/api/drafts"),
  get: (id: string) => request<Record<string, unknown>>(`/api/drafts/${id}`),
  generate: (task: string, cefr: string, topic: string) =>
    request<Record<string, unknown>>("/api/drafts/generate", json("POST", { task, cefr, topic })),
  approve: (id: string) => request<{ approved: string }>(`/api/drafts/${id}/approve`, json("POST")),
  discard: (id: string) => request<{ discarded: string }>(`/api/drafts/${id}`, json("DELETE")),
};

// ---- full mock test ----
export type MockPlan = {
  id: string; title: string; description: string; sections: string[]; reading: string; listening: string;
  writing: { build_sentence: string; email: string; discussion: string };
  speaking: { listen_repeat: string; interview: string };
};
export type MockAttempt = {
  id: string; created_at: string; mock_id: string; status: "in_progress" | "done";
  sections: Record<string, { response_ids: string[] }>; result: OverallBand | null;
  plan: MockPlan; next_section: string | null;
};

export const mock = {
  list: () => request<MockPlan[]>("/api/mocks"),
  start: (id: string) => request<{ attempt_id: string; plan: MockPlan; next_section: string }>(`/api/mocks/${id}/start`, json("POST")),
  get: (aid: string) => request<MockAttempt>(`/api/mocks/attempts/${aid}`),
  record: (aid: string, section: string, response_ids: string[]) =>
    request<{ next_section: string | null }>(`/api/mocks/attempts/${aid}/sections/${section}`, json("POST", { response_ids })),
  finish: (aid: string) => request<OverallBand>(`/api/mocks/attempts/${aid}/finish`, json("POST")),
};

// ---- progress ----
export type ProgressPoint = { id: string; date: string; score: number; max: number; pct: number };
export type Progress = {
  tasks: Record<string, { attempts: number; last_pct: number; best_pct: number; avg_pct: number; history: ProgressPoint[] }>;
  mocks: { id: string; date: string; mock_id: string; band: number; cefr: string; comparable_total: number;
           sections: Record<string, number> }[];
};
export const progressApi = { get: () => request<Progress>("/api/progress") };

// ---- human rating (calibration set) ----
export type RatePrompt =
  | { kind: "email"; scenario: string; recipient: string; points: string[] }
  | { kind: "discussion"; course: string; professor: Post; students: Post[] }
  | { kind: "interview"; question: string }
  | { kind: "listen-repeat"; sentence: string };
export type RateItem =
  | { done: true }
  | {
      done: false; remaining: number; response_id: string; task: string; prompt: RatePrompt;
      rubric: { bands: Record<string, string>; labels: Record<string, string> };
      text: string | null; transcript: string | null; has_audio: boolean;
    };
export type RatingStats = Record<string, { responses: number; unrated: number; rated_once: number; rated_twice_or_more: number }>;

export const ratings = {
  stats: () => request<RatingStats>("/api/ratings/stats"),
  next: (task: string, rater: string) =>
    request<RateItem>(`/api/ratings/next?task=${encodeURIComponent(task)}&rater=${encodeURIComponent(rater)}`),
  save: (response_id: string, rater: string, score: number, note?: string) =>
    request<{ ok: boolean }>("/api/ratings", json("POST", { response_id, rater, score, note })),
  export: () => request<Record<string, { rows: number; file: string | null }>>("/api/ratings/export", json("POST")),
};
