from typing import Any

import pytest

from subtitle_forge_api.domain import Transcript, TranscriptSegment
from subtitle_forge_api.translation import (
    OllamaTranslationProvider,
    TranslationValidationError,
)


class FakeStructuredClient:
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


def translated(*items: tuple[str, str]) -> dict[str, object]:
    return {"segments": [{"id": identifier, "translated_text": text} for identifier, text in items]}


def test_translation_preserves_exact_segment_identity_order_and_timestamps() -> None:
    source = transcript("Hello.", "How are you?")
    client = FakeStructuredClient(
        [
            translated(
                ("segment-000001", "您好。"),
                ("segment-000002", "你好嗎？"),
            )
        ]
    )

    result = OllamaTranslationProvider(client=client).translate(source)

    assert result.language == "zh-TW"
    assert [item.segment_id for item in result.segments] == [
        "segment-000001",
        "segment-000002",
    ]
    assert [(item.start_ms, item.end_ms) for item in result.segments] == [
        (0, 1_000),
        (1_000, 2_000),
    ]
    assert [item.translated_text for item in result.segments] == ["您好。", "你好嗎？"]
    assert "Traditional Chinese (zh-TW)" in client.calls[0][0]


def test_translation_batches_without_splitting_segments() -> None:
    source = transcript("alpha", "bravo", "charlie")
    client = FakeStructuredClient(
        [
            translated(("segment-000001", "甲")),
            translated(("segment-000002", "乙")),
            translated(("segment-000003", "丙")),
        ]
    )

    result = OllamaTranslationProvider(
        client=client,
        max_batch_chars=7,
    ).translate(source)

    assert len(client.calls) == 3
    assert [item.translated_text for item in result.segments] == ["甲", "乙", "丙"]


@pytest.mark.parametrize(
    "invalid",
    [
        translated(("segment-000001", "甲")),
        translated(("segment-000001", "甲"), ("segment-000001", "重複")),
        translated(("segment-000002", "乙"), ("segment-000001", "甲")),
        translated(("segment-000001", " "), ("segment-000002", "乙")),
        translated(
            ("segment-000001", "甲"),
            ("segment-000002", "乙"),
            ("segment-000003", "多餘"),
        ),
    ],
)
def test_one_invalid_alignment_gets_one_bounded_repair_retry(
    invalid: dict[str, object],
) -> None:
    source = transcript("alpha", "bravo")
    valid = translated(("segment-000001", "甲"), ("segment-000002", "乙"))
    client = FakeStructuredClient([invalid, valid])

    result = OllamaTranslationProvider(client=client).translate(source)

    assert [item.translated_text for item in result.segments] == ["甲", "乙"]
    assert len(client.calls) == 2
    assert "repair" in client.calls[1][0].lower()


def test_repeated_invalid_alignment_fails_after_exactly_one_retry() -> None:
    source = transcript("alpha", "bravo")
    invalid = translated(("segment-000001", "甲"))
    client = FakeStructuredClient([invalid, invalid])

    with pytest.raises(TranslationValidationError, match="align"):
        OllamaTranslationProvider(client=client).translate(source)

    assert len(client.calls) == 2


def test_response_timestamps_and_extra_fields_cannot_replace_source_timing() -> None:
    source = transcript("alpha")
    response = {
        "segments": [
            {
                "id": "segment-000001",
                "translated_text": "甲",
                "start_ms": 999_000,
                "end_ms": 1_000_000,
            }
        ]
    }
    client = FakeStructuredClient([response, translated(("segment-000001", "甲"))])

    result = OllamaTranslationProvider(client=client).translate(source)

    assert result.segments[0].start_ms == 0
    assert result.segments[0].end_ms == 1_000
    assert len(client.calls) == 2
