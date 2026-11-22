"""Paraphrased 2026 ETS writing rubrics (see docs/RUBRICS_2026.md). Bump RUBRIC_VERSION on any edit."""
from __future__ import annotations

from pydantic import BaseModel

RUBRIC_VERSION = "writing-2026.1"


class Dimension(BaseModel):
    id: str
    name: str
    looks_at: str


class Rubric(BaseModel):
    task: str
    title: str
    dimensions: list[Dimension]
    bands: dict[int, str]   # score → paraphrased descriptor
    labels: dict[int, str]


LABELS = {5: "Fully successful", 4: "Generally successful", 3: "Partially successful",
          2: "Mostly unsuccessful", 1: "Unsuccessful", 0: "No credit"}

ZERO = ("Blank, rejects or ignores the topic, not in English, entirely copied from the prompt, "
        "unconnected to the prompt, or random keystrokes.")

EMAIL = Rubric(
    task="write-an-email",
    title="Write an Email",
    labels=LABELS,
    dimensions=[
        Dimension(id="purpose", name="Task & elaboration",
                  looks_at="Does it address every required point, with elaboration that supports the communicative purpose?"),
        Dimension(id="conventions", name="Social conventions",
                  looks_at="Politeness, register and tone for the recipient; greeting/closing; organisation; how requests, "
                           "complaints or suggestions are phrased."),
        Dimension(id="range", name="Syntax & word choice",
                  looks_at="Variety of sentence structures; precise, idiomatic vocabulary."),
        Dimension(id="accuracy", name="Accuracy",
                  looks_at="Grammar, word forms, spelling and mechanics; do errors obscure meaning?"),
    ],
    bands={
        5: "Effective, clearly expressed, consistent facility. Elaboration fully supports the purpose; varied syntax; "
           "precise, idiomatic word choice; consistently appropriate social conventions; at most minor typos of the "
           "kind a competent writer makes under time pressure.",
        4: "Mostly effective and easily understood; language facility adequate to the task. Adequate elaboration; "
           "some syntactic variety and appropriate word choice; mostly appropriate social conventions; few errors.",
        3: "Generally accomplishes the task, but language limitations make parts unclear or less effective. "
           "Elaboration only partly supports the purpose; moderate range of syntax and vocabulary; noticeable errors "
           "in structure, word forms, idiom and/or social conventions.",
        2: "An attempt at the task that is mostly ineffective; the message is limited or hard to interpret. Limited or "
           "irrelevant elaboration; some connected sentence-level language but a limited range; accumulated errors.",
        1: "An ineffective attempt; the message may be close to unintelligible. Very little elaboration; telegraphic or "
           "disconnected phrases with a very limited vocabulary; serious, frequent errors; coherent language mostly "
           "borrowed from the prompt.",
        0: ZERO,
    },
)

DISCUSSION = Rubric(
    task="academic-discussion",
    title="Write for an Academic Discussion",
    labels=LABELS,
    dimensions=[
        Dimension(id="contribution", name="Relevance & contribution",
                  looks_at="Does it answer the professor's question with a clear position and add something to the "
                           "discussion (not just repeat the other students)?"),
        Dimension(id="elaboration", name="Elaboration",
                  looks_at="Explanations, examples and details that support the position; are any missing, unclear or "
                           "irrelevant?"),
        Dimension(id="range", name="Syntax & word choice",
                  looks_at="Variety of sentence structures; precise, idiomatic vocabulary."),
        Dimension(id="accuracy", name="Accuracy",
                  looks_at="Grammar, word forms, spelling and mechanics; do errors make ideas hard to follow?"),
    ],
    bands={
        5: "A relevant, very clearly expressed contribution with consistent facility. Well-elaborated explanations, "
           "examples and/or details; effective variety of structures; precise, idiomatic word choice; at most minor "
           "typos.",
        4: "A relevant contribution; ideas are easily understood. Relevant and adequately elaborated support; a "
           "variety of structures and appropriate word choice; few errors.",
        3: "A mostly relevant, mostly understandable contribution with some facility. Parts of the explanation or "
           "examples may be missing, unclear or irrelevant; some variety of structures and vocabulary; some noticeable "
           "errors.",
        2: "An attempt to contribute, but language limitations make ideas hard to follow. Ideas poorly elaborated or "
           "only partly relevant; limited range of structures and vocabulary; accumulated errors.",
        1: "An ineffective attempt; language limitations may prevent expression of ideas. Words and phrases with few "
           "or no coherent ideas; severely limited range; serious, frequent errors; coherent language mostly borrowed "
           "from the prompt.",
        0: ZERO,
    },
)

RUBRICS = {r.task: r for r in (EMAIL, DISCUSSION)}

SPEAKING_RUBRIC_VERSION = "speaking-2026.1"

INTERVIEW = Rubric(
    task="take-an-interview",
    title="Take an Interview",
    labels=LABELS,
    dimensions=[
        Dimension(id="relevance", name="Relevance & elaboration",
                  looks_at="Does the answer address the interviewer's question, stay on topic and elaborate with "
                           "reasons, details or examples (rather than reusing the question's words)?"),
        Dimension(id="fluency", name="Fluency & pace",
                  looks_at="Conversational pace; natural vs. long or frequent pauses; filler words; choppiness."),
        Dimension(id="intelligibility", name="Intelligibility",
                  looks_at="How easy the speech is to understand (estimated from transcript quality and recogniser "
                           "confidence — the rater cannot hear rhythm or intonation)."),
        Dimension(id="language", name="Grammar & vocabulary",
                  looks_at="Range and accuracy of grammar and vocabulary; precision of meaning; use of connectors."),
    ],
    bands={
        5: "Fully addresses the question; clear and fluent. On topic and well elaborated; good conversational pace with "
           "natural pauses; easily intelligible; a range of accurate grammar and vocabulary expresses precise meanings.",
        4: "Addresses the question and is reasonably clear. On topic and elaborated, though connectors between "
           "sentences may be weak; pace generally good with some pauses that affect flow; occasional words need minor "
           "listener effort; grammar and vocabulary adequate for general meanings.",
        3: "Addresses the question with limited elaboration and/or clarity. Generally on topic but elaboration may be "
           "limited; frequent or long pauses make it choppy, with filler words; intelligibility sometimes affected at "
           "word level; limited range and accuracy restrict precision.",
        2: "An attempt that is not supported in a meaningful or intelligible way. Minimally connected to the question, "
           "little relevant elaboration, or mostly reuses the question's language; intended meaning often hard to "
           "discern; very limited grammar and vocabulary.",
        1: "Minimally addresses the question with very limited language control. Only vaguely connected to the "
           "question; mostly unintelligible; mainly isolated words or phrases.",
        0: "No response, entirely unintelligible, no English, unconnected to the question, or only phrases such as "
           "\"I don't know\".",
    },
)

RUBRICS[INTERVIEW.task] = INTERVIEW


LISTEN_REPEAT_BANDS = {
    5: "Exact repetition; fully intelligible.",
    4: "Meaning fully captured but not exact: e.g. 1–2 small words missing/changed, a word ending (tense/number) "
       "changed, two words swapped, a key word replaced by a related word or missing in a long sentence, or 1–2 "
       "words hard to understand. Self-corrections are fine.",
    3: "Essentially the full sentence, but the meaning is not accurate: most key words present; several small words "
       "or at least one key word missing/changed; occasional intelligibility problems.",
    2: "A significant part missing and/or highly inaccurate (e.g. only the first part, then stops); not a full "
       "sentence; low intelligibility.",
    1: "Very little of the sentence, or largely unintelligible; a recognisable attempt.",
    0: "No response, unintelligible, no English, unrelated, or only \"I don't know\".",
}
