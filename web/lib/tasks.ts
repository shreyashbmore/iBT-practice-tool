// 2026 TOEFL iBT task catalogue — see docs/RUBRICS_2026.md
export type TaskDef = { id: string; name: string; scoring: string; ready: boolean };
export type SectionDef = { id: string; name: string; time: string; tasks: TaskDef[] };

export const SECTIONS: SectionDef[] = [
  {
    id: "reading", name: "Reading", time: "~30 min · adaptive",
    tasks: [
      { id: "complete-the-words", name: "Complete the Words", scoring: "auto", ready: true },
      { id: "read-daily-life", name: "Read in Daily Life", scoring: "auto", ready: true },
      { id: "read-academic-passage", name: "Read an Academic Passage", scoring: "auto", ready: true },
    ],
  },
  {
    id: "listening", name: "Listening", time: "~29 min · adaptive",
    tasks: [
      { id: "listen-choose-response", name: "Listen and Choose a Response", scoring: "auto", ready: true },
      { id: "listen-conversation", name: "Listen to a Conversation", scoring: "auto", ready: true },
      { id: "listen-announcement", name: "Listen to an Announcement", scoring: "auto", ready: true },
      { id: "listen-academic-talk", name: "Listen to an Academic Talk", scoring: "auto", ready: true },
    ],
  },
  {
    id: "writing", name: "Writing", time: "~23 min",
    tasks: [
      { id: "build-a-sentence", name: "Build a Sentence", scoring: "0/1 each", ready: true },
      { id: "write-an-email", name: "Write an Email", scoring: "0–5 rubric", ready: true },
      { id: "academic-discussion", name: "Write for an Academic Discussion", scoring: "0–5 rubric", ready: true },
    ],
  },
  {
    id: "speaking", name: "Speaking", time: "~8 min",
    tasks: [
      { id: "listen-and-repeat", name: "Listen and Repeat", scoring: "0–5 each", ready: true },
      { id: "take-an-interview", name: "Take an Interview", scoring: "0–5 each", ready: true },
    ],
  },
];

export const findTask = (id: string) => SECTIONS.flatMap((s) => s.tasks).find((t) => t.id === id);

export const taskName = (id: string) =>
  findTask(id)?.name ?? ({ "reading-test": "Reading section test", "listening-test": "Listening section test",
    "mock-test": "Full mock test" } as
    Record<string, string>)[id] ?? id;

export const OBJECTIVE_TASKS = new Set([
  "complete-the-words", "read-daily-life", "read-academic-passage",
  "listen-choose-response", "listen-conversation", "listen-announcement", "listen-academic-talk",
]);
