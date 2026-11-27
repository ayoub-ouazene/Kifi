"""Unit tests for ``steps/clean.py`` (the ``clean_messages`` ZenML step).

Run from ``knowledge_pipeline/``::

    uv run --with pytest pytest src/kifi_knwolegde_pipeline/testing -v

Hermetic by design
------------------
``clean.py`` imports ``zenml``, ``loguru`` and ``llm_twin``. None of those are
needed to test the cleaning logic, and ``llm_twin`` is not even installed in
this repo, so they are replaced by tiny fakes *only while clean.py is being
imported* (``sys.modules`` is restored afterwards). The tests therefore need
nothing but ``pytest``.

Layout
------
* ``TestFixMojibake`` / ``TestShouldDropContent`` / ``TestCleanTextContent`` /
  ``TestMergeGroup``      -> the four private helpers, in isolation.
* ``TestDocumentFilters`` / ``TestMessageProcessing`` / ``TestMerging`` /
  ``TestMojibakeInPipeline`` / ``TestDocumentHandling`` / ``TestStepMetadata``
  / ``TestEndToEnd``      -> the ``clean_messages`` step itself.
* ``TestKnownLimitations`` -> behaviour that looks unintended today. Those
  tests pin what the code *currently* does so a change is noticed; if you fix
  the underlying behaviour, update or delete the matching test.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

CLEAN_PY = Path(__file__).resolve().parents[1] / "steps" / "clean.py"


# ---------------------------------------------------------------------------
# Fakes for the third-party modules clean.py imports
# ---------------------------------------------------------------------------
class FakeMessagesDocument:
    """Stand-in for ``llm_twin.domain.documents.MessagesDocument``.

    Only the surface ``clean_messages`` touches is modelled: ``id``,
    ``participant_name``, ``messages`` and ``set_composite_id()``. The latter
    records what it saw so tests can check *when* it was called, and derives a
    deterministic id from the current content like the real one is expected to.
    """

    def __init__(self, *, id, participant_name, messages):
        self.id = id
        self.participant_name = participant_name
        self.messages = messages
        self.composite_id_calls: list[dict] = []

    def set_composite_id(self) -> None:
        self.composite_id_calls.append(
            {
                "id_before": self.id,
                "participant_name": self.participant_name,
                "messages": copy.deepcopy(self.messages),
            }
        )
        payload = json.dumps(
            [self.participant_name, self.messages], sort_keys=True, ensure_ascii=False
        )
        self.id = "composite-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def _load_clean_module() -> types.ModuleType:
    """Import clean.py by path with fake zenml / loguru / llm_twin in place."""
    loguru = types.ModuleType("loguru")
    loguru.logger = MagicMock(name="logger")

    zenml = types.ModuleType("zenml")

    def step(fn=None, **_kwargs):  # supports both @step and @step(...)
        return (lambda f: f) if fn is None else fn

    def get_step_context():  # real zenml raises outside of a running step
        raise RuntimeError("get_step_context() can only be called inside a step.")

    zenml.step = step
    zenml.get_step_context = get_step_context

    llm_twin = types.ModuleType("llm_twin")
    domain = types.ModuleType("llm_twin.domain")
    documents = types.ModuleType("llm_twin.domain.documents")
    documents.MessagesDocument = FakeMessagesDocument
    llm_twin.domain = domain
    domain.documents = documents

    fakes = {
        "loguru": loguru,
        "zenml": zenml,
        "llm_twin": llm_twin,
        "llm_twin.domain": domain,
        "llm_twin.domain.documents": documents,
    }
    spec = importlib.util.spec_from_file_location("kifi_clean_under_test", CLEAN_PY)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, fakes):
        spec.loader.exec_module(module)
    return module


clean = _load_clean_module()


@pytest.fixture(autouse=True)
def _reset_logger():
    clean.logger.reset_mock()


@pytest.fixture
def step_context(monkeypatch):
    """Make ``get_step_context()`` return a mock (as it would inside a pipeline)."""
    ctx = MagicMock(name="step_context")
    monkeypatch.setattr(clean, "get_step_context", lambda: ctx)
    return ctx


# ---------------------------------------------------------------------------
# Test-data helpers
# ---------------------------------------------------------------------------
MINUTE = 60_000
T0 = 1_700_000_000_000  # an arbitrary "conversation start" timestamp (ms)
MIN_MESSAGES = 100  # step 2: documents with fewer raw messages are skipped
FILLER_PREFIX = "filler message"
FILLER_START = T0 + 30 * 24 * 60 * MINUTE  # far away from any test message


def P(case_id: str, *values):
    """``pytest.param`` with a readable id."""
    return pytest.param(*values, id=case_id)


def garble(text: str, codec: str = "latin-1") -> str:
    """Produce Facebook/Meta-style mojibake: UTF-8 bytes mis-read as latin-1."""
    return text.encode("utf-8").decode(codec)


def msg(sender, ts, content, **extra) -> dict:
    return {"sender_name": sender, "timestamp_ms": ts, "content": content, **extra}


def filler(n: int, senders=("Alice", "Bob")) -> list[dict]:
    """``n`` valid messages, 10 min apart (never merged), far after the test data."""
    return [
        msg(senders[i % len(senders)], FILLER_START + i * 10 * MINUTE, f"{FILLER_PREFIX} {i + 1}")
        for i in range(n)
    ]


def make_doc(messages, participant_name="Bob", doc_id="raw-id", pad=True):
    """Build a document, padding it with filler so it clears the 100-message rule.

    Filler reuses the senders already present (so it can't change the
    participant count) and sits ~30 days later (so it can't merge with the
    messages under test). Use ``body()`` to strip it from the output again.
    """
    messages = list(messages)
    if pad:
        senders = list(
            dict.fromkeys(m.get("sender_name") for m in messages if m.get("sender_name") is not None)
        ) or ["Alice", "Bob"]
        messages += filler(max(0, MIN_MESSAGES - len(messages)), senders)
    return clean.MessagesDocument(id=doc_id, participant_name=participant_name, messages=messages)


def body(doc) -> list[dict]:
    """A cleaned document's messages, minus the padding added by ``make_doc``."""
    return [m for m in doc.messages if not m["content"].startswith(FILLER_PREFIX)]


def run(*docs):
    return clean.clean_messages(list(docs))


def out(sender, ts, content, participant="Bob") -> dict:
    """Expected shape of one cleaned message."""
    return {
        "sender_name": sender,
        "timestamp_ms": ts,
        "content": content,
        "participant_name": participant,
    }


# ===========================================================================
# _fix_mojibake
# ===========================================================================
class TestFixMojibake:
    @pytest.mark.parametrize(
        ("garbled", "expected"),
        [
            P("accents", "Ã©tÃ©", "été"),
            P("grave-accent", "piÃ¨ce jointe", "pièce jointe"),
            P("cedilla", "FranÃ§ois", "François"),
            P("sentence", "Ã§a va trÃ¨s bien", "ça va très bien"),
            P("cp1252-curly-apostrophe", garble("It’s", "cp1252"), "It’s"),
            P("latin1-curly-apostrophe", garble("It’s"), "It’s"),
            P("emoji", garble("😀"), "😀"),
            P("emoji-sequence", garble("😂👍❤"), "😂👍❤"),
            # byte 0x81 is undefined in cp1252, so only the latin-1 fallback can fix it
            P("latin1-fallback-A-acute", garble("Á"), "Á"),
            P("arabic", garble("مرحبا"), "مرحبا"),
            P("trailing-newline", "Ã©\n", "é\n"),
            P("multiline", "Ã©tÃ©\ntrÃ¨s", "été\ntrès"),
        ],
    )
    def test_repairs_utf8_read_as_latin1_or_cp1252(self, garbled, expected):
        assert clean._fix_mojibake(garbled) == expected

    @pytest.mark.parametrize(
        "text",
        [
            P("empty", ""),
            P("ascii", "hello world"),
            P("ascii-newlines", "line1\r\nline2"),
            P("whitespace", "   "),
            P("already-correct-accents", "été"),
            P("already-correct-name", "François"),
            P("arabic", "مرحبا"),
            P("emoji", "😀"),
            P("cjk", "日本語"),
            P("garbled-plus-unencodable-emoji", "Ã© 😀"),
            P("half-garbled-trailing-lead-byte", "Ã"),
            P("correct-and-garbled-mixed", "été Ã©tÃ©"),
        ],
    )
    def test_leaves_text_that_is_not_mojibake_untouched(self, text):
        assert clean._fix_mojibake(text) == text

    @pytest.mark.parametrize("value", [P("none", None), P("zero", 0), P("int", 42), P("bytes", b"abc")])
    def test_non_string_input_is_returned_unchanged_and_never_raises(self, value):
        assert clean._fix_mojibake(value) == value

    @pytest.mark.parametrize("original", ["été", "François", "It’s", "😀", "مرحبا"])
    def test_is_idempotent(self, original):
        once = clean._fix_mojibake(garble(original))
        assert clean._fix_mojibake(once) == once == original


# ===========================================================================
# _should_drop_content
# ===========================================================================
DROP_CASES = [
    # -- not a string at all ------------------------------------------------
    P("none", None),
    P("int", 123),
    P("float", 4.5),
    P("float-nan", float("nan")),
    P("bool", True),
    P("list", ["hi"]),
    P("dict", {"a": 1}),
    P("bytes", b"hello"),
    # -- empty / single character (after stripping quotes, (edited), spaces) -
    P("empty", ""),
    P("space", " "),
    P("mixed-whitespace", " \n\t "),
    P("single-char", "a"),
    P("single-char-padded", "  a  "),
    P("single-emoji", "👍"),
    P("single-double-quote", '"'),
    P("only-double-quotes", '""'),
    P("quoted-single-char", '"a"'),
    P("only-edited", "(edited)"),
    P("padded-edited", "  (edited)  "),
    P("quoted-edited", '"(edited)"'),
    P("single-char-then-edited", "a (edited)"),
    # -- NaN / None / NULL strings (any case, padded, quoted) ----------------
    P("NAN", "NAN"),
    P("nan", "nan"),
    P("NaN", "NaN"),
    P("None", "None"),
    P("none-lower", "none"),
    P("NULL", "NULL"),
    P("null-lower", "null"),
    P("null-padded", "  null  "),
    P("null-quoted", '"NULL"'),
    P("nan-edited", "nan (edited)"),
    # -- exact blacklist ------------------------------------------------------
    P("bl-attachment-mojibake", "Vous avez envoyÃ© une piÃ¨ce jointe."),
    P("bl-attachment-fr", "Vous avez envoyé une pièce jointe."),
    P("bl-audio-call-ended", "Audio call ended"),
    P("bl-phone-number", "00799999004417259635"),
    P("bl-nonoletop", "nonoletop2.2"),
    P("bl-missed-video-chat", "You missed a video chat"),
    P("bl-liked-a-message", "Liked a message"),
    P("bl-padded", "  Liked a message  "),
    P("bl-quoted", '"Audio call ended"'),
    P("bl-with-edited-marker", "Liked a message (edited)"),
    # -- "Reacted <x> to your message" --------------------------------------
    P("reacted-heart", "Reacted ❤ to your message"),
    P("reacted-emoji-trailing-space", "Reacted 😂 to your message "),
    P("reacted-mojibake-emoji", "Reacted " + garble("😂") + " to your message"),
    P("reacted-no-emoji", "Reacted to your message"),
    P("reacted-quoted", '"Reacted ❤ to your message"'),
    # only the regex branch catches these: the startswith("Reacted ") fallback needs a plain space
    P("reacted-tab-separated", "Reacted\t❤\tto your message"),
    P("reacted-newline-separated", "Reacted\n❤\nto your message"),
    P("reacted-nbsp-separated", "Reacted ❤ to your message"),
    # -- links ---------------------------------------------------------------
    P("link-http", "http://example.com"),
    P("link-https", "https://example.com/path?x=1&y=2"),
    P("link-bare-https-colon", "https:"),
    P("link-bare-http-colon", "http:"),
    P("link-www", "www.google.com"),
    P("link-inside-sentence", "check this out www.example.com now"),
    P("link-after-text", "see https://a.b for details"),
    P("link-quoted", 'Look: "https://x.y"'),
    # -- attachment notices ---------------------------------------------------
    P("attach-named-fr", "Ayoub a envoyé une pièce jointe."),
    P("attach-named-mojibake", "Ayoub a envoyÃ© une piÃ¨ce jointe."),
    P("attach-multiword-name", "Sarah Ben Ali a envoyé une pièce jointe."),
    P("attach-suffix-only", "a envoyé une pièce jointe."),
    # -- audio call notices ---------------------------------------------------
    P("audio-call-named", "Ayoub started an audio call"),
    P("audio-call-suffix-only", "started an audio call"),
    # -- gmail addresses ------------------------------------------------------
    P("gmail-plain", "foo@gmail.com"),
    P("gmail-in-sentence", "write me at foo@gmail.com please"),
    P("gmail-domain-only", "@gmail.com"),
]

KEEP_CASES = [
    # -- ordinary chat --------------------------------------------------------
    P("two-chars", "ok"),
    P("hi", "hi"),
    P("salam", "Salam"),
    P("question", "How are you?"),
    P("french", "ça va ?"),
    P("arabic", "مرحبا"),
    P("two-emoji", "😀😀"),
    P("with-spaces", "a b"),
    P("contains-quotes", 'I said "hello"'),
    P("contains-edited-and-text", "see you (edited) tomorrow"),
    P("long-text", "this is a perfectly normal message " * 5),
    P("apostrophe", "it's fine"),
    # -- looks like NaN/None/NULL but isn't -----------------------------------
    P("nanny", "nanny"),
    P("none-of-your-business", "none of your business"),
    P("nullable", "nullable"),
    P("nan-bread", "Nan bread"),
    P("nan-sentence", "NaN is not a number"),
    # -- near-misses of the exact blacklist (matching is exact + case-sensitive)
    P("audio-call-ended-lowercase", "audio call ended"),
    P("audio-call-ended-period", "Audio call ended."),
    P("liked-a-message-exclaim", "Liked a message!"),
    P("missed-video-chat-today", "You missed a video chat today"),
    P("audio-call-partial", "Audio call"),
    P("attachment-no-period", "Vous avez envoyé une pièce jointe"),
    P("nonoletop-extended", "nonoletop2.2 lol"),
    # -- near-misses of "Reacted ... to your message" -------------------------
    P("reacted-not-at-start", "I Reacted ❤ to your message"),
    P("reacted-lowercase", "reacted ❤ to your message"),
    P("reacted-to-their-message", "Reacted ❤ to their message"),
    P("reacted-alone", "Reacted"),
    P("reacted-without-tail", "Reacted ❤"),
    # -- near-misses of the link rule ----------------------------------------
    P("http-word", "http is a protocol"),
    P("https-word", "https"),
    P("www-word", "www"),
    P("domain-without-scheme", "example.com"),
    P("ftp-link", "ftp://example.com"),
    # -- near-misses of the gmail rule ---------------------------------------
    P("yahoo", "foo@yahoo.com"),
    P("gmail-without-at", "gmail.com"),
    P("gmail-word", "gmail"),
    # -- near-misses of the suffix rules --------------------------------------
    P("audio-call-then-more", "started an audio call yesterday"),
    P("attachment-suffix-no-period", "Ayoub a envoyé une pièce jointe"),
]


class TestShouldDropContent:
    @pytest.mark.parametrize("content", DROP_CASES)
    def test_drops(self, content):
        assert clean._should_drop_content(content) is True

    @pytest.mark.parametrize("content", KEEP_CASES)
    def test_keeps(self, content):
        assert clean._should_drop_content(content) is False


# ===========================================================================
# _clean_text_content
# ===========================================================================
class TestCleanTextContent:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # -- double quotes ---------------------------------------------------
            P("quotes-removed", 'say "hi"', "say hi"),
            P("only-quotes", '""""', ""),
            P("single-quote-chars-kept", "it's 'fine'", "it's 'fine'"),
            # -- the "(edited)" marker ------------------------------------------
            P("edited-suffix-spaced", "hello (edited)", "hello"),
            P("edited-suffix-attached", "hello(edited)", "hello"),
            P("edited-prefix", "(edited) hello", "hello"),
            P("edited-only", "(edited)", ""),
            P("edited-in-middle", "hel(edited)lo", "hello"),
            P("edited-twice", "a (edited) b (edited)", "a  b"),
            P("edited-is-case-sensitive", "(Edited)", "(Edited)"),
            P("edit-is-not-edited", "hello (edit)", "hello (edit)"),
            # -- stripping ------------------------------------------------------
            P("strip-spaces", "  hi  ", "hi"),
            P("strip-newlines-tabs", "\n\thi\r\n", "hi"),
            P("inner-whitespace-kept", "hi  there", "hi  there"),
            P("empty", "", ""),
            P("whitespace-only", "   ", ""),
            # -- collapsing runs of 4+ identical characters to 2 ----------------
            P("run-of-5", "hhhhh", "hh"),
            P("run-of-4-is-collapsed", "hhhh", "hh"),
            P("run-of-3-is-kept", "hhh", "hhh"),
            P("run-of-2-is-kept", "hh", "hh"),
            P("single-char", "h", "h"),
            P("run-inside-word", "heyyyyyy", "heyy"),
            P("run-then-more-text", "noooooo way", "noo way"),
            P("two-separate-runs", "aaaa bbbb", "aa bb"),
            P("adjacent-different-runs", "aaaabbbb", "aabb"),
            P("punctuation", "!!!!!!", "!!"),
            P("question-marks", "?????", "??"),
            P("dots", "....", ".."),
            P("emoji-run", "😂😂😂😂😂", "😂😂"),
            P("arabic-laughter", "ههههههه", "هه"),
            P("uppercase-run", "AAAA", "AA"),
            P("case-sensitive-runs", "aAaA", "aAaA"),
            P("alternating-not-a-run", "hahahaha", "hahahaha"),
            P("run-of-spaces", "a     b", "a  b"),
            P("run-of-newlines", "a\n\n\n\nb", "a\n\nb"),
            P("multiline-untouched", "line1\nline2", "line1\nline2"),
            # -- the sub-steps feed each other (quotes/(edited) go first) ---------
            P("quotes-removed-before-collapse", 'h"h"h"h', "hh"),
            P("edited-removed-before-collapse", "ll(edited)ll", "ll"),
            P("edited-then-strip", " (edited) hi", "hi"),
            # -- things it must NOT touch -----------------------------------------
            P("accents-untouched", "été", "été"),
            P("arabic-untouched", "مرحبا", "مرحبا"),
            P("mojibake-untouched-here", "Ã©", "Ã©"),
        ],
    )
    def test_cleaning(self, raw, expected):
        assert clean._clean_text_content(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        ['say "hi" (edited)', "yesssssss!!!!!!", "  a\n\n\n\nb  ", "😂😂😂😂😂 (edited)", "plain text"],
    )
    def test_is_idempotent(self, raw):
        once = clean._clean_text_content(raw)
        assert clean._clean_text_content(once) == once


# ===========================================================================
# _merge_group
# ===========================================================================
class TestMergeGroup:
    def test_single_message_group_is_returned_as_is(self):
        only = msg("Alice", 1000, "hello", participant_name="Bob")
        assert clean._merge_group([only], "ignored") is only

    def test_joins_contents_with_newlines_in_order(self):
        group = [msg("Alice", 1000, "one"), msg("Alice", 2000, "two"), msg("Alice", 3000, "three")]
        assert clean._merge_group(group, "Bob")["content"] == "one\ntwo\nthree"

    def test_result_has_exactly_the_four_expected_keys(self):
        merged = clean._merge_group([msg("Alice", 1, "a1"), msg("Alice", 2, "a2")], "Bob")
        assert set(merged) == {"sender_name", "timestamp_ms", "content", "participant_name"}

    def test_sender_comes_from_the_first_message(self):
        group = [msg("Alice", 1, "x1"), msg("Carol", 2, "x2")]
        assert clean._merge_group(group, "Bob")["sender_name"] == "Alice"

    def test_participant_name_comes_from_the_argument_not_the_messages(self):
        group = [
            msg("Alice", 1, "x1", participant_name="stale"),
            msg("Alice", 2, "x2", participant_name="stale"),
        ]
        assert clean._merge_group(group, "Fresh")["participant_name"] == "Fresh"

    @pytest.mark.parametrize(
        ("timestamps", "expected"),
        [
            P("two-values", [1000, 3000], 2000),
            P("three-values", [1000, 2000, 6000], 3000),
            P("rounds-up", [0, 1, 1], 1),  # 0.67 -> 1
            P("rounds-down", [0, 0, 1], 0),  # 0.33 -> 0
            P("identical", [5000, 5000, 5000], 5000),
        ],
    )
    def test_timestamp_is_the_rounded_mean(self, timestamps, expected):
        group = [msg("Alice", t, f"m{i}") for i, t in enumerate(timestamps)]
        merged = clean._merge_group(group, "Bob")
        assert merged["timestamp_ms"] == expected
        assert isinstance(merged["timestamp_ms"], int)

    def test_empty_and_none_contents_are_skipped_when_joining(self):
        group = [
            msg("Alice", 1, "a1"),
            msg("Alice", 2, ""),
            msg("Alice", 3, None),
            msg("Alice", 4, "b1"),
        ]
        assert clean._merge_group(group, "Bob")["content"] == "a1\nb1"

    def test_all_contents_empty_gives_empty_string(self):
        group = [msg("Alice", 1, ""), msg("Alice", 2, None)]
        assert clean._merge_group(group, "Bob")["content"] == ""

    def test_missing_content_key_is_treated_as_empty(self):
        group = [{"sender_name": "Alice", "timestamp_ms": 1}, msg("Alice", 2, "x1")]
        assert clean._merge_group(group, "Bob")["content"] == "x1"

    def test_missing_timestamp_key_counts_as_zero(self):
        group = [msg("Alice", 100, "a1"), {"sender_name": "Alice", "content": "a2"}]
        assert clean._merge_group(group, "Bob")["timestamp_ms"] == 50

    def test_merged_content_is_cleaned_again(self):
        # Runs/edges that only appear once the pieces are joined get normalised.
        group = [msg("Alice", 1, "x\n\n"), msg("Alice", 2, "\n\ny")]
        assert clean._merge_group(group, "Bob")["content"] == "x\n\ny"

    def test_merged_content_is_stripped_quotes_and_edited_removed(self):
        group = [msg("Alice", 1, '  "a1"'), msg("Alice", 2, "b1 (edited)  ")]
        assert clean._merge_group(group, "Bob")["content"] == "a1\nb1"

    def test_does_not_mutate_its_input(self):
        group = [msg("Alice", 1, "a1"), msg("Alice", 2, "b1")]
        snapshot = copy.deepcopy(group)
        clean._merge_group(group, "Bob")
        assert group == snapshot


# ===========================================================================
# clean_messages -- document-level filters (steps 1 & 2)
# ===========================================================================
class TestDocumentFilters:
    def test_document_with_more_than_two_unique_senders_is_skipped(self):
        doc = make_doc([msg("Alice", T0, "hello"), msg("Bob", T0 + MINUTE, "hi"), msg("Carol", T0 + 2 * MINUTE, "yo")])
        assert run(doc) == []

    def test_skipping_for_participants_is_logged_with_doc_id_and_count(self):
        doc = make_doc(
            [msg("Alice", T0, "hello"), msg("Bob", T0 + MINUTE, "hi"), msg("Carol", T0 + 2 * MINUTE, "yo")],
            doc_id="group-chat",
        )
        run(doc)
        logged = " ".join(str(c.args[0]) for c in clean.logger.info.call_args_list)
        assert "group-chat" in logged
        assert "more than 1 participant" in logged
        assert "3 unique senders" in logged

    def test_exactly_two_senders_is_kept(self):
        doc = make_doc([msg("Alice", T0, "hello"), msg("Bob", T0 + 10 * MINUTE, "hi there")])
        assert run(doc) == [doc]

    def test_a_single_sender_is_kept(self):
        doc = make_doc([msg("Alice", T0, "hello"), msg("Alice", T0 + 10 * MINUTE, "anyone there")])
        assert run(doc) == [doc]

    def test_messages_with_no_sender_do_not_count_as_a_participant(self):
        doc = make_doc(
            [
                msg("Alice", T0, "hello"),
                msg("Bob", T0 + 10 * MINUTE, "hi there"),
                msg(None, T0 + 20 * MINUTE, "who am i"),
                {"timestamp_ms": T0 + 30 * MINUTE, "content": "no sender key"},
            ]
        )
        assert run(doc) == [doc]

    def test_document_where_nobody_has_a_sender_is_kept(self):
        doc = make_doc(
            [msg(None, T0, "hello there"), msg(None, T0 + 10 * MINUTE, "general kenobi")], pad=False
        )
        doc.messages += [msg(None, FILLER_START + i * 10 * MINUTE, f"{FILLER_PREFIX} {i}") for i in range(98)]
        (result,) = run(doc)
        assert [m["sender_name"] for m in result.messages] == [None] * 100

    def test_empty_string_sender_still_counts_as_a_participant(self):
        doc = make_doc([msg("Alice", T0, "hello"), msg("Bob", T0 + 10 * MINUTE, "hi"), msg("", T0 + 20 * MINUTE, "who")])
        assert run(doc) == []

    @pytest.mark.parametrize(
        ("count", "kept"),
        [
            P("zero", 0, False),
            P("one", 1, False),
            P("ninety-nine", 99, False),
            P("exactly-one-hundred", 100, True),
            P("one-hundred-and-one", 101, True),
            P("many", 500, True),
        ],
    )
    def test_minimum_message_count_boundary(self, count, kept):
        doc = make_doc(filler(count), pad=False)
        assert (run(doc) == [doc]) is kept

    def test_skipping_for_too_few_messages_is_logged(self):
        run(make_doc(filler(99), pad=False, doc_id="tiny"))
        logged = " ".join(str(c.args[0]) for c in clean.logger.info.call_args_list)
        assert "tiny" in logged
        assert "too few messages" in logged
        assert "99 < 100" in logged

    def test_minimum_is_counted_on_raw_messages_before_junk_is_dropped(self):
        junk = [msg("Alice", T0 + i * 10 * MINUTE, "Liked a message") for i in range(99)]
        keeper = msg("Bob", T0 + 1000 * MINUTE, "the only real message")
        (result,) = run(make_doc(junk + [keeper], pad=False))
        assert result.messages == [out("Bob", T0 + 1000 * MINUTE, "the only real message")]

    def test_document_whose_messages_all_get_dropped_is_removed(self):
        junk = [msg("Alice" if i % 2 else "Bob", T0 + i * 10 * MINUTE, "Liked a message") for i in range(100)]
        assert run(make_doc(junk, pad=False)) == []

    def test_document_with_no_messages_is_removed(self):
        assert run(make_doc([], pad=False)) == []

    def test_skipped_documents_are_left_completely_untouched(self):
        raw = [msg("Alice", T0, '"hello" (edited)'), msg("Bob", T0 + MINUTE, "yesssss")]
        doc = make_doc(raw, pad=False, doc_id="keep-me", participant_name="Bob")
        snapshot = copy.deepcopy(doc.messages)
        run(doc)
        assert doc.id == "keep-me"
        assert doc.messages == snapshot
        assert doc.composite_id_calls == []


# ===========================================================================
# clean_messages -- per-message processing (step 3)
# ===========================================================================
class TestMessageProcessing:
    def test_output_keeps_only_the_four_expected_fields(self):
        raw = msg(
            "Alice",
            T0,
            "hello there",
            type="Generic",
            is_geoblocked_for_viewer=False,
            reactions=[{"reaction": "❤", "actor": "Bob"}],
            photos=[{"uri": "photos/1.jpg"}],
            share={"link": "x"},
        )
        (result,) = run(make_doc([raw]))
        assert body(result) == [out("Alice", T0, "hello there")]
        assert set(body(result)[0]) == {"sender_name", "timestamp_ms", "content", "participant_name"}

    def test_participant_name_comes_from_the_document(self):
        (result,) = run(make_doc([msg("Alice", T0, "hello there")], participant_name="Sarah"))
        assert body(result)[0]["participant_name"] == "Sarah"

    @pytest.mark.parametrize(
        "bad_content",
        [P("none", None), P("int", 42), P("float", 1.5), P("list", ["x"]), P("bytes", b"hello")],
    )
    def test_messages_with_missing_or_non_string_content_are_dropped(self, bad_content):
        (result,) = run(make_doc([msg("Alice", T0, bad_content), msg("Bob", T0 + 10 * MINUTE, "real one")]))
        assert body(result) == [out("Bob", T0 + 10 * MINUTE, "real one")]

    def test_photo_or_sticker_message_without_a_content_key_is_dropped(self):
        photo_only = {"sender_name": "Alice", "timestamp_ms": T0, "photos": [{"uri": "a.jpg"}]}
        (result,) = run(make_doc([photo_only, msg("Bob", T0 + 10 * MINUTE, "real one")]))
        assert body(result) == [out("Bob", T0 + 10 * MINUTE, "real one")]

    @pytest.mark.parametrize(
        "junk",
        [
            P("empty", ""),
            P("single-char", "k"),
            P("quotes-only", '""'),
            P("edited-only", "(edited)"),
            P("nan", "nan"),
            P("null", "NULL"),
            P("attachment", garble("Vous avez envoyé une pièce jointe.")),
            P("named-attachment", "Sarah a envoyé une pièce jointe."),
            P("audio-call-ended", "Audio call ended"),
            P("audio-call-started", "Sarah started an audio call"),
            P("missed-video-chat", "You missed a video chat"),
            P("liked", "Liked a message"),
            P("reaction", "Reacted 😂 to your message"),
            P("link", "https://example.com"),
            P("www", "www.example.com"),
            P("gmail", "me@gmail.com"),
        ],
    )
    def test_system_noise_is_removed(self, junk):
        (result,) = run(make_doc([msg("Alice", T0, junk), msg("Bob", T0 + 10 * MINUTE, "real one")]))
        assert body(result) == [out("Bob", T0 + 10 * MINUTE, "real one")]

    def test_quotes_edited_marker_and_repeats_are_cleaned_in_the_pipeline(self):
        raw = msg("Alice", T0, '  "heyyyyyy" (edited)  ')
        (result,) = run(make_doc([raw]))
        assert body(result) == [out("Alice", T0, "heyy")]

    def test_non_ascii_content_survives(self):
        arabic = "مرحبا كيف حالك"
        french = "ça va très bien, merci"
        (result,) = run(
            make_doc([msg("Alice", T0, arabic), msg("Bob", T0 + 10 * MINUTE, french)])
        )
        assert [m["content"] for m in body(result)] == [arabic, french]

    def test_dropping_a_message_does_not_affect_neighbouring_kept_messages(self):
        msgs = [
            msg("Alice", T0, "first"),
            msg("Bob", T0 + 10 * MINUTE, "Liked a message"),
            msg("Alice", T0 + 20 * MINUTE, "second"),
        ]
        (result,) = run(make_doc(msgs))
        assert [m["content"] for m in body(result)] == ["first", "second"]

    def test_message_content_is_never_empty_in_the_output(self):
        msgs = [msg("Alice", T0 + i * 10 * MINUTE, c) for i, c in enumerate(['""', "(edited)", " ", "ok", "👍", "fine"])]
        (result,) = run(make_doc(msgs))
        assert all(len(m["content"]) > 1 for m in result.messages)
        assert [m["content"] for m in body(result)] == ["ok", "fine"]


# ===========================================================================
# clean_messages -- sorting & merging
# ===========================================================================
class TestMerging:
    def test_same_sender_within_two_minutes_is_merged(self):
        doc = make_doc([msg("Alice", T0, "hello"), msg("Alice", T0 + MINUTE, "how are you")])
        (result,) = run(doc)
        assert body(result) == [out("Alice", T0 + 30_000, "hello\nhow are you")]

    @pytest.mark.parametrize("gap", [P("simultaneous", 0), P("one-ms", 1), P("just-under", 119_999), P("exactly-two-min", 120_000)])
    def test_gap_up_to_and_including_two_minutes_merges(self, gap):
        (result,) = run(make_doc([msg("Alice", T0, "first"), msg("Alice", T0 + gap, "second")]))
        assert [m["content"] for m in body(result)] == ["first\nsecond"]

    @pytest.mark.parametrize("gap", [P("one-ms-over", 120_001), P("three-min", 3 * MINUTE), P("ten-min", 10 * MINUTE), P("a-day", 24 * 60 * MINUTE)])
    def test_gap_over_two_minutes_does_not_merge(self, gap):
        (result,) = run(make_doc([msg("Alice", T0, "first"), msg("Alice", T0 + gap, "second")]))
        assert [m["content"] for m in body(result)] == ["first", "second"]

    def test_different_senders_are_never_merged_even_at_the_same_instant(self):
        (result,) = run(make_doc([msg("Alice", T0, "hello"), msg("Bob", T0, "hi there")]))
        assert body(result) == [out("Alice", T0, "hello"), out("Bob", T0, "hi there")]

    def test_other_sender_in_between_splits_the_group(self):
        msgs = [msg("Alice", T0, "one"), msg("Bob", T0 + 10_000, "two"), msg("Alice", T0 + 20_000, "three")]
        (result,) = run(make_doc(msgs))
        assert [(m["sender_name"], m["content"]) for m in body(result)] == [
            ("Alice", "one"),
            ("Bob", "two"),
            ("Alice", "three"),
        ]

    def test_a_dropped_message_from_the_other_sender_does_not_split_the_group(self):
        msgs = [
            msg("Alice", T0, "hello"),
            msg("Bob", T0 + 30_000, "Liked a message"),  # removed before merging
            msg("Alice", T0 + 100_000, "world"),
        ]
        (result,) = run(make_doc(msgs))
        assert body(result) == [out("Alice", T0 + 50_000, "hello\nworld")]

    def test_gap_is_measured_from_the_previous_message_not_the_group_start(self):
        # 0 -> 100s -> 200s: each hop is < 2 min although the span is 200s.
        msgs = [msg("Alice", T0, "one"), msg("Alice", T0 + 100_000, "two"), msg("Alice", T0 + 200_000, "three")]
        (result,) = run(make_doc(msgs))
        assert body(result) == [out("Alice", T0 + 100_000, "one\ntwo\nthree")]

    def test_a_long_gap_in_the_middle_closes_the_group(self):
        msgs = [
            msg("Alice", T0, "one"),
            msg("Alice", T0 + MINUTE, "two"),
            msg("Alice", T0 + 10 * MINUTE, "three"),
            msg("Alice", T0 + 11 * MINUTE, "four"),
        ]
        (result,) = run(make_doc(msgs))
        assert [m["content"] for m in body(result)] == ["one\ntwo", "three\nfour"]

    def test_merged_timestamp_is_the_rounded_mean(self):
        msgs = [msg("Alice", T0, "aa"), msg("Alice", T0 + 1, "bb"), msg("Alice", T0 + 1, "cc")]  # mean = T0 + 0.67
        (result,) = run(make_doc(msgs))
        assert body(result)[0]["timestamp_ms"] == T0 + 1
        assert isinstance(body(result)[0]["timestamp_ms"], int)

    def test_unsorted_input_is_sorted_by_timestamp(self):
        msgs = [
            msg("Bob", T0 + 20 * MINUTE, "third"),
            msg("Alice", T0, "first"),
            msg("Bob", T0 + 10 * MINUTE, "second"),
        ]
        (result,) = run(make_doc(msgs))
        assert [m["content"] for m in body(result)] == ["first", "second", "third"]

    def test_unsorted_input_still_merges_the_right_messages(self):
        msgs = [msg("Alice", T0 + MINUTE, "world"), msg("Alice", T0, "hello")]
        (result,) = run(make_doc(msgs))
        assert body(result) == [out("Alice", T0 + 30_000, "hello\nworld")]

    def test_equal_timestamps_keep_their_input_order(self):
        (result,) = run(make_doc([msg("Alice", T0, "one"), msg("Alice", T0, "two")]))
        assert body(result)[0]["content"] == "one\ntwo"
        (result,) = run(make_doc([msg("Alice", T0, "two"), msg("Alice", T0, "one")]))
        assert body(result)[0]["content"] == "two\none"

    def test_realistic_alternating_conversation(self):
        msgs = [
            msg("Alice", T0, "a-one"),
            msg("Alice", T0 + MINUTE, "a-two"),
            msg("Bob", T0 + 2 * MINUTE, "b-one"),
            msg("Bob", T0 + 10 * MINUTE, "b-two"),
            msg("Alice", T0 + 11 * MINUTE, "a-three"),
        ]
        (result,) = run(make_doc(msgs))
        assert body(result) == [
            out("Alice", T0 + 30_000, "a-one\na-two"),
            out("Bob", T0 + 2 * MINUTE, "b-one"),
            out("Bob", T0 + 10 * MINUTE, "b-two"),
            out("Alice", T0 + 11 * MINUTE, "a-three"),
        ]

    def test_merged_output_is_in_ascending_time_order(self):
        (result,) = run(make_doc([msg("Alice" if i % 2 else "Bob", T0 + i * 7 * MINUTE, f"m{i:02d}") for i in range(30)]))
        stamps = [m["timestamp_ms"] for m in result.messages]
        assert stamps == sorted(stamps)

    def test_documents_are_merged_independently(self):
        d1 = make_doc([msg("Alice", T0, "d1 hello")], doc_id="d1", participant_name="Bob")
        d2 = make_doc([msg("Alice", T0 + MINUTE, "d2 hello")], doc_id="d2", participant_name="Carol")
        r1, r2 = run(d1, d2)
        assert [m["content"] for m in body(r1)] == ["d1 hello"]
        assert [m["content"] for m in body(r2)] == ["d2 hello"]


# ===========================================================================
# clean_messages -- mojibake repair (step 5, runs last)
# ===========================================================================
class TestMojibakeInPipeline:
    def test_content_sender_and_participant_are_all_repaired(self):
        sender = garble("François")
        doc = make_doc(
            [msg(sender, T0, garble("été très chaud")), msg("Alice", T0 + 10 * MINUTE, "ok then")],
            participant_name=garble("François"),
        )
        (result,) = run(doc)
        assert body(result) == [
            out("François", T0, "été très chaud", participant="François"),
            out("Alice", T0 + 10 * MINUTE, "ok then", participant="François"),
        ]
        assert result.participant_name == "François"

    def test_merged_messages_are_repaired_as_a_whole(self):
        doc = make_doc([msg("Alice", T0, garble("été")), msg("Alice", T0 + MINUTE, garble("très chaud"))])
        (result,) = run(doc)
        assert body(result)[0]["content"] == "été\ntrès chaud"

    def test_already_correct_text_is_left_alone(self):
        (result,) = run(make_doc([msg("François", T0, "café été")], participant_name="François"))
        assert body(result) == [out("François", T0, "café été", participant="François")]

    def test_each_field_is_repaired_independently(self):
        # content is already fine / unfixable, sender is garbled: sender still gets fixed
        (result,) = run(make_doc([msg(garble("Aïcha"), T0, "été 😀")]))
        assert body(result)[0]["sender_name"] == "Aïcha"
        assert body(result)[0]["content"] == "été 😀"

    def test_arabic_mojibake_is_repaired(self):
        (result,) = run(make_doc([msg("Alice", T0, garble("مرحبا كيف حالك"))]))
        assert body(result)[0]["content"] == "مرحبا كيف حالك"

    def test_blacklist_is_checked_on_the_still_garbled_text(self):
        # Hence the mojibake variants in the blacklist: this must be dropped.
        garbled_notice = garble("Vous avez envoyé une pièce jointe.")
        (result,) = run(make_doc([msg("Alice", T0, garbled_notice)]))
        assert body(result) == []

    def test_none_participant_name_does_not_crash(self):
        (result,) = run(make_doc([msg("Alice", T0, "hello there")], participant_name=None))
        assert result.participant_name is None
        assert body(result)[0]["participant_name"] is None

    def test_none_sender_stays_none(self):
        (result,) = run(make_doc([msg(None, T0, "hello there")]))
        assert body(result)[0]["sender_name"] is None


# ===========================================================================
# clean_messages -- document handling & composite id
# ===========================================================================
class TestDocumentHandling:
    def test_empty_input_returns_an_empty_list(self):
        assert clean.clean_messages([]) == []

    def test_returns_a_list(self):
        assert isinstance(run(make_doc([msg("Alice", T0, "hello there")])), list)

    def test_id_is_reset_and_composite_id_recomputed_on_the_cleaned_content(self):
        doc = make_doc([msg(garble("Zoé"), T0, garble("été")), msg("Bob", T0 + 10 * MINUTE, "hi")], doc_id="raw-id", participant_name=garble("Zoé"))
        (result,) = run(doc)

        assert len(result.composite_id_calls) == 1
        seen = result.composite_id_calls[0]
        assert seen["id_before"] is None  # id was cleared first
        assert seen["messages"] == result.messages  # computed on the cleaned messages
        assert seen["participant_name"] == "Zoé"  # ... with the repaired participant name
        assert result.id != "raw-id"
        assert result.id.startswith("composite-")

    def test_composite_id_is_computed_once_per_kept_document(self):
        docs = [make_doc([msg("Alice", T0, f"doc {i} hello")], doc_id=f"raw-{i}") for i in range(3)]
        results = run(*docs)
        assert [len(d.composite_id_calls) for d in results] == [1, 1, 1]

    def test_returned_documents_are_the_input_objects_cleaned_in_place(self):
        doc = make_doc([msg("Alice", T0, '"hello" (edited)')])
        (result,) = run(doc)
        assert result is doc
        assert body(doc)[0]["content"] == "hello"

    def test_mixed_batch_keeps_only_valid_documents_in_input_order(self):
        good_a = make_doc([msg("Alice", T0, "good a")], doc_id="good-a")
        too_few = make_doc(filler(50), pad=False, doc_id="too-few")
        good_b = make_doc([msg("Alice", T0, "good b")], doc_id="good-b")
        group = make_doc([msg("A", T0, "x1"), msg("B", T0, "x2"), msg("C", T0, "x3")], doc_id="group")
        all_junk = make_doc([msg("Alice" if i % 2 else "Bob", T0 + i * 10 * MINUTE, "Liked a message") for i in range(100)], pad=False, doc_id="junk")
        results = run(good_a, too_few, good_b, group, all_junk)
        assert results == [good_a, good_b]
        assert [d.id for d in results] != ["good-a", "good-b"]  # ids were recomputed

    def test_identical_content_yields_identical_ids_and_different_content_does_not(self):
        same_1 = make_doc([msg("Alice", T0, "hello there")], doc_id="x")
        same_2 = make_doc([msg("Alice", T0, "hello there")], doc_id="y")
        other = make_doc([msg("Alice", T0, "something else")], doc_id="z")
        r1, r2, r3 = run(same_1, same_2, other)
        assert r1.id == r2.id
        assert r1.id != r3.id


# ===========================================================================
# clean_messages -- ZenML step metadata
# ===========================================================================
class TestStepMetadata:
    def test_reports_raw_and_cleaned_document_counts(self, step_context):
        good = make_doc([msg("Alice", T0, "hello there")])
        too_few = make_doc(filler(10), pad=False)
        also_good = make_doc([msg("Bob", T0, "hi there")])
        run(good, too_few, also_good)
        step_context.add_output_metadata.assert_called_once_with(
            output_name="cleaned_messages",
            metadata={"num_raw_documents": 3, "num_cleaned_documents": 2},
        )

    def test_empty_input_reports_zero_counts(self, step_context):
        clean.clean_messages([])
        step_context.add_output_metadata.assert_called_once_with(
            output_name="cleaned_messages",
            metadata={"num_raw_documents": 0, "num_cleaned_documents": 0},
        )

    def test_works_outside_a_running_step_and_logs_a_warning(self):
        # No ``step_context`` fixture: get_step_context() raises, like real ZenML does.
        doc = make_doc([msg("Alice", T0, "hello there")])
        assert run(doc) == [doc]
        warning = str(clean.logger.warning.call_args.args[0])
        assert "Failed to add step metadata" in warning

    def test_failure_while_adding_metadata_does_not_lose_the_results(self, step_context):
        step_context.add_output_metadata.side_effect = RuntimeError("metadata store is down")
        doc = make_doc([msg("Alice", T0, "hello there")])
        assert run(doc) == [doc]
        warning = str(clean.logger.warning.call_args.args[0])
        assert "Failed to add step metadata" in warning
        assert "metadata store is down" in warning


# ===========================================================================
# End to end: one realistic conversation exercising every rule at once
# ===========================================================================
class TestEndToEnd:
    def test_realistic_conversation(self):
        me, her = "Moncef", "Sarah"
        raw = [
            msg(me, T0, "Salam!!!!!!"),  # repeats collapsed
            msg(me, T0 + 30_000, garble('ça va ? (edited)')),  # (edited) removed, mojibake repaired
            msg(her, T0 + 1 * MINUTE, "Liked a message"),  # dropped: blacklist
            msg(her, T0 + 2 * MINUTE, garble("Vous avez envoyé une pièce jointe.")),  # dropped: attachment
            msg(her, T0 + 3 * MINUTE, "https://example.com/video"),  # dropped: link
            msg(her, T0 + 4 * MINUTE, "yesssss"),  # kept, collapsed
            {"sender_name": her, "timestamp_ms": T0 + 5 * MINUTE, "photos": [{"uri": "a.jpg"}]},  # dropped: no content
            msg(me, T0 + 30 * MINUTE, "👍"),  # dropped: single character
            msg(her, T0 + 31 * MINUTE, "Reacted ❤ to your message"),  # dropped: reaction
            msg(her, T0 + 31 * MINUTE + 30_000, "lol"),
            msg(her, T0 + 32 * MINUTE, '"haha"'),
        ]
        doc = make_doc(raw, participant_name=her)
        (result,) = run(doc)

        assert body(result) == [
            out(me, T0 + 15_000, "Salam!!\nça va ?", participant=her),
            out(her, T0 + 4 * MINUTE, "yess", participant=her),
            out(her, T0 + 31 * MINUTE + 45_000, "lol\nhaha", participant=her),
        ]
        assert len(result.composite_id_calls) == 1


# ===========================================================================
# Behaviour that looks unintended today -- pinned so a change is noticed.
# ===========================================================================
class TestKnownLimitations:
    """If you fix one of these on purpose, update or delete the matching test."""

    def test_www_inside_a_word_is_mistaken_for_a_link(self):
        # "awww." contains "www." so an affectionate message is thrown away.
        assert clean._should_drop_content("awww. so cute") is True

    @pytest.mark.parametrize("content", ["HTTPS://EXAMPLE.COM", "Visit WWW.EXAMPLE.COM", "Foo@Gmail.com"])
    def test_link_and_gmail_detection_is_case_sensitive(self, content):
        assert clean._should_drop_content(content) is False

    @pytest.mark.parametrize(
        ("raw", "collapsed"),
        [
            P("twenty-thousand", "20000 DA", "200 DA"),
            P("one-million", "1000000", "100"),
            P("ten-thousand", "10000", "100"),
            P("three-zeros-are-safe", "2000", "2000"),  # a run needs 4+ identical characters
        ],
    )
    def test_runs_of_repeated_digits_are_collapsed_which_corrupts_numbers(self, raw, collapsed):
        assert clean._clean_text_content(raw) == collapsed

    def test_single_emoji_survives_when_it_is_still_mojibake_encoded(self):
        # Length is checked before the mojibake repair: "👍" is 1 char (dropped) but its
        # garbled form is 4 chars (kept), and only afterwards becomes a 1-char message.
        assert clean._should_drop_content("👍") is True
        (result,) = run(make_doc([msg("Alice", T0, garble("👍"))]))
        assert body(result) == [out("Alice", T0, "👍")]

    def test_repeated_emoji_are_not_collapsed_when_mojibake_encoded(self):
        # Collapsing runs happens before the mojibake repair, when the repeated emoji
        # are still multi-char sequences that don't look like a run.
        (plain,) = run(make_doc([msg("Alice", T0, "😂" * 5)]))
        (garbled,) = run(make_doc([msg("Alice", T0, garble("😂" * 5))]))
        assert body(plain)[0]["content"] == "😂😂"
        assert body(garbled)[0]["content"] == "😂" * 5

    @pytest.mark.xfail(
        raises=TypeError,
        strict=False,
        reason="A message without a timestamp makes the sort compare None with int and "
        "crashes the whole step. Passing (XPASS) means this was made robust.",
    )
    def test_message_without_a_timestamp_should_not_crash_the_step(self):
        doc = make_doc([msg("Alice", None, "no timestamp here"), msg("Bob", T0, "this one has one")])
        run(doc)
