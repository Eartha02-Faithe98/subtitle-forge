from typing import Any, Literal

import pytest

from subtitle_forge_api.domain import Transcript, TranscriptSegment
from subtitle_forge_api.summarization import (
    OllamaSummaryProvider,
    SummaryValidationError,
)


class FakeSummaryClient:
    def __init__(self, responses: list[dict[str, Any] | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, object]] = []

    def generate_json(self, prompt: str, schema: object) -> dict[str, Any]:
        self.calls.append((prompt, schema))
        response = self.responses[len(self.calls) - 1]
        if isinstance(response, Exception):
            raise response
        return response


def transcript(*texts: str) -> Transcript:
    return Transcript(
        segments=tuple(
            TranscriptSegment(
                segment_id=f"segment-{index:06d}",
                start_ms=(index - 1) * 1_000,
                end_ms=index * 1_000,
                source_text=text,
            )
            for index, text in enumerate(texts, start=1)
        )
    )


@pytest.mark.parametrize(
    ("language", "text", "language_instruction"),
    [
        ("en", "A concise English summary.", "English"),
        ("zh-TW", "一段精簡的繁體中文摘要。", "Traditional Chinese (zh-TW)"),
    ],
)
def test_short_transcript_produces_one_plain_language_labeled_summary(
    language: Literal["en", "zh-TW"],
    text: str,
    language_instruction: str,
) -> None:
    client = FakeSummaryClient([{"summary": text}])

    result = OllamaSummaryProvider(client=client).summarize(
        transcript("A short transcript."),
        language,
    )

    assert result.language == language
    assert result.text == text
    assert len(client.calls) == 1
    prompt = client.calls[0][0]
    assert language_instruction in prompt
    assert "Do not add chapters" in prompt
    assert "timestamp citations" in prompt


def test_long_transcript_uses_bounded_map_reduce() -> None:
    client = FakeSummaryClient(
        [
            {"summary": "Map A"},
            {"summary": "Map B"},
            {"summary": "Map C"},
            {"summary": "Reduced summary"},
        ]
    )

    result = OllamaSummaryProvider(
        client=client,
        max_batch_chars=5,
    ).summarize(transcript("aaaaa", "bbbbb", "ccccc"), "en")

    assert result.text == "Reduced summary"
    assert len(client.calls) == 4
    assert all("aaaaabbbbb" not in prompt for prompt, _schema in client.calls)
    assert "Map A" in client.calls[-1][0]
    assert "Map B" in client.calls[-1][0]
    assert "Map C" in client.calls[-1][0]


@pytest.mark.parametrize(
    "response",
    [
        {"summary": ""},
        {"summary": "   "},
        {"summary": "Text", "chapters": []},
        {"chapters": []},
    ],
)
def test_empty_or_phase_two_structured_output_is_rejected(
    response: dict[str, object],
) -> None:
    with pytest.raises(SummaryValidationError, match="summary"):
        OllamaSummaryProvider(client=FakeSummaryClient([response])).summarize(
            transcript("source"),
            "en",
        )


def test_provider_failure_propagates_without_being_rewritten() -> None:
    failure = RuntimeError("safe provider boundary failure")

    with pytest.raises(RuntimeError, match="safe provider boundary failure"):
        OllamaSummaryProvider(client=FakeSummaryClient([failure])).summarize(
            transcript("source"),
            "zh-TW",
        )


def test_segment_larger_than_batch_limit_fails_before_provider_call() -> None:
    client = FakeSummaryClient([])

    with pytest.raises(SummaryValidationError, match="batch limit"):
        OllamaSummaryProvider(client=client, max_batch_chars=5).summarize(
            transcript("too long"),
            "en",
        )

    assert client.calls == []
