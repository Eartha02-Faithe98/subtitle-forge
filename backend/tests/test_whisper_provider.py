from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from subtitle_forge_api.domain import WhisperProfile
from subtitle_forge_api.whisper import (
    FasterWhisperProvider,
    WhisperUnavailableError,
)

MODEL_MAP = {"fast": "base.en", "balanced": "small.en", "accurate": "medium.en"}


class FakeModel:
    def __init__(
        self,
        segments: list[object] | None = None,
        *,
        error: Exception | None = None,
        duration: float = 2.0,
    ) -> None:
        self.segments = segments or []
        self.error = error
        self.duration = duration
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def transcribe(self, audio: str, **options: Any) -> tuple[list[object], object]:
        self.calls.append((audio, options))
        if self.error is not None:
            raise self.error
        return self.segments, SimpleNamespace(duration=self.duration)


class FakeModelFactory:
    def __init__(
        self,
        model: FakeModel | None = None,
        error: Exception | None = None,
    ) -> None:
        self.model = model or FakeModel()
        self.error = error
        self.calls: list[tuple[str, str, str, bool]] = []

    def __call__(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        local_files_only: bool,
    ) -> FakeModel:
        self.calls.append((model_name, device, compute_type, local_files_only))
        if self.error is not None:
            raise self.error
        return self.model


def raw_segment(
    start: float,
    end: float,
    text: str,
    words: list[object] | None = None,
) -> object:
    return SimpleNamespace(start=start, end=end, text=text, words=words)


def raw_word(start: float, end: float, word: str) -> object:
    return SimpleNamespace(start=start, end=end, word=word)


@pytest.mark.parametrize(
    ("profile", "model_name"),
    [
        (WhisperProfile.FAST, "base.en"),
        (WhisperProfile.BALANCED, "small.en"),
        (WhisperProfile.ACCURATE, "medium.en"),
    ],
)
def test_profiles_use_local_cpu_safe_model_mapping(
    tmp_path: Path,
    profile: WhisperProfile,
    model_name: str,
) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFFfixture")
    model = FakeModel([raw_segment(0.0, 1.0, "Hello")])
    factory = FakeModelFactory(model)

    FasterWhisperProvider(
        profile=profile,
        model_map=MODEL_MAP,
        model_factory=factory,
    ).transcribe(audio)

    assert factory.calls == [(model_name, "cpu", "int8", True)]
    _, options = model.calls[0]
    assert options["language"] == "en"
    assert options["word_timestamps"] is True


def test_normalizes_segments_words_and_reports_bounded_progress(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFFfixture")
    model = FakeModel(
        [
            raw_segment(
                0.125,
                1.25,
                " Hello world ",
                [raw_word(0.125, 0.5, " Hello"), raw_word(0.6, 1.25, " world")],
            ),
            raw_segment(1.25, 2.0, "Again"),
        ],
        duration=2.0,
    )
    progress: list[float] = []

    transcript = FasterWhisperProvider(
        profile=WhisperProfile.BALANCED,
        model_map=MODEL_MAP,
        model_factory=FakeModelFactory(model),
    ).transcribe(audio, progress.append)

    assert transcript.language == "en"
    assert [item.segment_id for item in transcript.segments] == [
        "whisper-000001",
        "whisper-000002",
    ]
    assert [(item.start_ms, item.end_ms, item.source_text) for item in transcript.segments] == [
        (125, 1_250, "Hello world"),
        (1_250, 2_000, "Again"),
    ]
    assert [(word.start_ms, word.end_ms, word.text) for word in transcript.segments[0].words] == [
        (125, 500, "Hello"),
        (600, 1_250, "world"),
    ]
    assert progress == [0.0, 0.625, 1.0, 1.0]
    assert all(0.0 <= value <= 1.0 for value in progress)


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            FakeModelFactory(error=FileNotFoundError("C:\\secret\\models\\small.en")),
            "not available locally",
        ),
        (
            FakeModelFactory(FakeModel(error=RuntimeError("C:\\secret\\audio.wav"))),
            "could not transcribe",
        ),
        (FakeModelFactory(FakeModel([])), "recognizable English speech"),
    ],
)
def test_missing_model_runtime_failure_and_silence_are_safe(
    tmp_path: Path,
    factory: FakeModelFactory,
    message: str,
) -> None:
    audio = tmp_path / "private-audio.wav"
    audio.write_bytes(b"RIFFfixture")

    with pytest.raises(WhisperUnavailableError, match=message) as captured:
        FasterWhisperProvider(
            profile=WhisperProfile.BALANCED,
            model_map=MODEL_MAP,
            model_factory=factory,
        ).transcribe(audio)

    assert "secret" not in str(captured.value)
    assert str(audio) not in str(captured.value)


def test_missing_audio_is_rejected_before_loading_model(tmp_path: Path) -> None:
    factory = FakeModelFactory()

    with pytest.raises(WhisperUnavailableError, match="unavailable"):
        FasterWhisperProvider(
            profile=WhisperProfile.FAST,
            model_map=MODEL_MAP,
            model_factory=factory,
        ).transcribe(tmp_path / "missing.wav")

    assert factory.calls == []
