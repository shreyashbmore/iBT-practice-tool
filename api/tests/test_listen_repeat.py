import pytest

from app.providers.speech.base import Transcript, Word
from app.scoring.listen_repeat import normalize, score

TARGET = "If you need help choosing your classes, make an appointment with an advisor."


def tr(text: str, low: set[str] = frozenset()) -> Transcript:
    words = [Word(word=w, start=i * 0.4, end=i * 0.4 + 0.3, confidence=0.3 if w in low else 0.95)
             for i, w in enumerate(text.split())]
    return Transcript(text=text, words=words)


def test_normalize():
    assert normalize("You're first-year students’ guide!") == ["you", "are", "first", "year", "students", "guide"]


@pytest.mark.parametrize("said,expected", [
    ("if you need help choosing your classes make an appointment with an advisor", 5),
    ("um if you need help choosing your classes uh make an appointment with an advisor", 5),   # fillers ignored
    ("if you you need help choosing your classes make an appointment with an advisor", 5),     # repetition ignored
    ("if you need help choosing your classes make appointment with advisor", 4),               # 2 function words
    ("if you need help choosing your class make an appointment with an advisor", 4),           # inflection
    ("if you need help choosing classes make an appointment with the advisor", 4),
    ("if you need help with your classes make an appointment with an advisor", 4),             # 1 content word (long)
    ("you need help your classes make appointment advisor", 3),                                 # most content, full
    ("if you need help choosing your classes", 2),                                              # stops halfway
    ("help classes", 1),
    ("I really like pizza", 0),
    ("", 0),
])
def test_bands(said, expected):
    r = score(TARGET, tr(said))
    assert r.score == expected, (said, r.stats, r.reasons)


def test_low_confidence_drops_exact_to_4():
    r = score(TARGET, tr("if you need help choosing your classes make an appointment with an advisor", low={"appointment"}))
    assert r.score == 4 and r.stats.low_confidence == 1


def test_short_sentence_content_miss_is_not_4():
    r = score("Welcome to the student center.", tr("welcome to the center"))
    assert r.score == 3


def test_transposition_counts_as_moved():
    r = score("The library is open every day until midnight.", tr("the library is open until midnight every day"))
    assert r.stats.moved >= 1 and r.score >= 3
    ops = [t.op for t in r.tokens]
    assert "moved" in ops


def test_tokens_for_ui():
    r = score("Welcome to the student center.", tr("welcome to student centre"))
    assert [(t.op, t.expected) for t in r.tokens if t.expected] == [
        ("match", "welcome"), ("match", "to"), ("del", "the"), ("match", "student"), ("sub", "center")]
