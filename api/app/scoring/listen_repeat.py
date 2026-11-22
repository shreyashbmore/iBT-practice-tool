"""Listen and Repeat: deterministic scorer (no LLM).

Aligns the verbatim transcript to the target sentence, classifies every difference
(content vs function word, inflection change, moved word, extra word) and maps the counts
to the 0–5 rubric (docs/RUBRICS_2026.md §6). Thresholds are config so they can be tuned in week 7.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

from app.providers.speech.base import Transcript

FILLERS = {"uh", "um", "uhm", "erm", "er", "ah", "hmm", "mm", "mhm"}

FUNCTION_WORDS = set("""
a an the this that these those some any each every no another such
i me my mine you your yours he him his she her hers it its we us our ours they them their theirs
myself yourself himself herself itself ourselves themselves one ones
who whom whose which what where when why how whether
am is are was were be been being have has had having do does did done will would shall should
can could may might must ought
and or but nor so yet if because although though while since unless until as than then
of in on at to for from by with about into onto over under through during before after above below
between among against without within along across around near off up down out upon via per
not too very also just only even there here all both either neither much many more most less least few
""".split())

CONTRACTIONS = {
    "i'm": "i am", "you're": "you are", "we're": "we are", "they're": "they are", "he's": "he is",
    "she's": "she is", "it's": "it is", "that's": "that is", "there's": "there is", "what's": "what is",
    "i've": "i have", "you've": "you have", "we've": "we have", "they've": "they have",
    "i'll": "i will", "you'll": "you will", "we'll": "we will", "they'll": "they will", "it'll": "it will",
    "i'd": "i would", "you'd": "you would", "we'd": "we would", "they'd": "they would",
    "can't": "can not", "cannot": "can not", "won't": "will not", "don't": "do not", "doesn't": "does not",
    "didn't": "did not", "isn't": "is not", "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "haven't": "have not", "hasn't": "has not", "hadn't": "had not", "shouldn't": "should not",
    "wouldn't": "would not", "couldn't": "could not", "let's": "let us",
}

Op = Literal["match", "inflect", "sub", "del", "ins", "moved", "repeat"]


class AlignedToken(BaseModel):
    op: Op
    expected: str | None = None
    heard: str | None = None
    content: bool = False
    confidence: float | None = None


class LRStats(BaseModel):
    target_words: int
    content_words: int
    content_ok: int
    content_missing: int
    function_errors: int
    inflections: int
    moved: int
    extra_words: int
    low_confidence: int
    full_sentence: bool


class ListenRepeatResult(BaseModel):
    score: int
    max_score: int = 5
    target: str
    transcript: str
    tokens: list[AlignedToken]
    stats: LRStats
    reasons: list[str]
    scorer: str = "listen-repeat-rules-v1"


class Thresholds(BaseModel):
    """Tunable cut-offs (see `python -m app.evals.tune_lr`)."""
    low_conf: float = 0.5               # word confidence below this = unclear
    min_content_for_one_miss: int = 6   # a content-word miss is still a 4 only in longer stimuli
    max_minor_for_4: int = 2            # function-word / inflection / order changes allowed at 4
    ratio_for_3: float = 0.5            # share of content words needed for a 3 (with full sentence)
    ratio_for_2: float = 1 / 3          # share of content words needed for a 2


DEFAULT = Thresholds()
LOW_CONF = DEFAULT.low_conf


def normalize(text: str) -> list[str]:
    t = text.lower().replace("’", "'").replace("‘", "'")
    t = re.sub(r"[-–—/]", " ", t)
    out: list[str] = []
    for w in re.findall(r"[a-z0-9']+", t):
        w = w.strip("'")
        if not w:
            continue
        out.extend(CONTRACTIONS.get(w, w).split())
    return out


def _stem(w: str) -> str:
    for suf in ("ies", "ing", "ed", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _is_content(w: str) -> bool:
    return w not in FUNCTION_WORDS


def _hyp_tokens(t: Transcript) -> list[tuple[str, float]]:
    toks: list[tuple[str, float]] = []
    for w in t.words:
        for n in normalize(w.word):
            if n not in FILLERS:
                toks.append((n, w.confidence))
    if not t.words and t.text:  # transcript without word timings
        toks = [(n, 1.0) for n in normalize(t.text) if n not in FILLERS]
    return toks


def align(ref: list[str], hyp: list[tuple[str, float]]) -> list[AlignedToken]:
    n, m = len(ref), len(hyp)
    INF = float("inf")
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back: list[list[str | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0
    for i in range(n + 1):
        for j in range(m + 1):
            c = cost[i][j]
            if c == INF:
                continue
            if i < n and j < m:
                r, h = ref[i], hyp[j][0]
                op, add = ("match", 0) if r == h else (("inflect", 0.5) if _stem(r) == _stem(h) else ("sub", 1.01))  # tiny bias: prefer del+ins pairs on ties (lets us detect moved words)
                if c + add < cost[i + 1][j + 1]:
                    cost[i + 1][j + 1], back[i + 1][j + 1] = c + add, op
            if i < n and c + 1 < cost[i + 1][j]:
                cost[i + 1][j], back[i + 1][j] = c + 1, "del"
            if j < m and c + 1 < cost[i][j + 1]:
                cost[i][j + 1], back[i][j + 1] = c + 1, "ins"
    ops: list[AlignedToken] = []
    i, j = n, m
    while i > 0 or j > 0:
        op = back[i][j]
        if op in ("match", "inflect", "sub"):
            ops.append(AlignedToken(op=op, expected=ref[i - 1], heard=hyp[j - 1][0],
                                    content=_is_content(ref[i - 1]), confidence=hyp[j - 1][1]))
            i, j = i - 1, j - 1
        elif op == "del":
            ops.append(AlignedToken(op="del", expected=ref[i - 1], content=_is_content(ref[i - 1])))
            i -= 1
        else:
            ops.append(AlignedToken(op="ins", heard=hyp[j - 1][0], confidence=hyp[j - 1][1]))
            j -= 1
    ops.reverse()

    # repeated words / self-corrections ("the the", "I go I went") are not penalised
    prev_heard = None
    for k, t in enumerate(ops):
        if t.op == "ins" and (t.heard == prev_heard or
                              (k + 1 < len(ops) and ops[k + 1].heard == t.heard)):
            t.op = "repeat"
        if t.heard:
            prev_heard = t.heard
    # a deleted word that was said elsewhere = moved (transposition)
    ins_idx = {}
    for k, t in enumerate(ops):
        if t.op == "ins":
            ins_idx.setdefault(t.heard, []).append(k)
    for t in ops:
        if t.op == "del" and ins_idx.get(t.expected):
            k = ins_idx[t.expected].pop(0)
            t.op, t.heard, t.confidence = "moved", ops[k].heard, ops[k].confidence
            ops[k].op = "repeat"  # counted once, via the moved token
            ops[k].heard = None
    return [t for t in ops if not (t.op == "repeat" and t.heard is None)]


def score(target: str, transcript: Transcript, th: Thresholds = DEFAULT) -> ListenRepeatResult:
    ref = normalize(target)
    hyp = _hyp_tokens(transcript)
    tokens = align(ref, hyp) if hyp else [AlignedToken(op="del", expected=w, content=_is_content(w)) for w in ref]

    content = [t for t in tokens if t.expected and t.content]
    content_ok = sum(t.op in ("match", "moved", "inflect") for t in content)
    stats = LRStats(
        target_words=len(ref),
        content_words=len(content),
        content_ok=content_ok,
        content_missing=len(content) - content_ok,
        function_errors=sum(t.op in ("sub", "del") for t in tokens if t.expected and not t.content),
        inflections=sum(t.op == "inflect" for t in tokens),
        moved=sum(t.op == "moved" for t in tokens),
        extra_words=sum(t.op == "ins" for t in tokens),
        low_confidence=sum(t.op == "match" and t.content and (t.confidence or 1) < th.low_conf for t in tokens),
        full_sentence=_full_sentence(tokens),
    )
    s, reasons = _rubric(stats, matched_any=any(t.op in ("match", "inflect", "moved") for t in tokens), th=th)
    return ListenRepeatResult(score=s, target=target, transcript=transcript.text, tokens=tokens,
                              stats=stats, reasons=reasons)


def _full_sentence(tokens: list[AlignedToken]) -> bool:
    """The response reaches the end of the sentence: one of the last two content words was said."""
    last = [t for t in tokens if t.expected and t.content][-2:]
    return any(t.op in ("match", "inflect", "moved") for t in last)


def _rubric(s: LRStats, matched_any: bool, th: Thresholds = DEFAULT) -> tuple[int, list[str]]:
    if not matched_any:
        return 0, ["Nothing in the response matched the sentence."]
    ratio = s.content_ok / s.content_words if s.content_words else 1.0
    minor = s.function_errors + s.inflections + s.moved
    exact = (s.content_missing == 0 and minor == 0 and s.extra_words == 0)
    if exact and s.low_confidence == 0:
        return 5, ["Exact repetition, clearly pronounced."]
    allowed_miss = 1 if s.content_words >= th.min_content_for_one_miss else 0
    if (s.content_missing <= allowed_miss and minor <= th.max_minor_for_4 and s.extra_words <= 2
            and s.low_confidence <= 2):
        why = []
        if s.function_errors:
            why.append(f"{s.function_errors} small word(s) missing or changed")
        if s.inflections:
            why.append(f"{s.inflections} word ending(s) changed (tense/number)")
        if s.moved:
            why.append("word order changed")
        if s.content_missing:
            why.append("one key word missing or changed")
        if s.extra_words:
            why.append(f"{s.extra_words} extra word(s)")
        if s.low_confidence:
            why.append(f"{s.low_confidence} word(s) unclear")
        return 4, ["Meaning fully kept, but not exact: " + ", ".join(why) + "."]
    if ratio >= th.ratio_for_3 and s.full_sentence:
        return 3, [f"Most key words were repeated ({s.content_ok}/{s.content_words}), but the meaning changed or "
                   f"several words were missing."]
    if ratio >= th.ratio_for_2:
        return 2, [f"A significant part is missing ({s.content_ok}/{s.content_words} key words)"
                   + ("" if s.full_sentence else "; the end of the sentence was not repeated") + "."]
    return 1, [f"Very little of the sentence was repeated ({s.content_ok}/{s.content_words} key words)."]
