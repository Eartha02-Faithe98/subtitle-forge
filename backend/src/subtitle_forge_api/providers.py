"""Replaceable local provider capability contracts for Phase 1."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from subtitle_forge_api.domain import (
    Summary,
    Transcript,
    TranslatedTranscript,
    WhisperProfile,
)

ProgressCallback = Callable[[float], None]
SummaryLanguage = Literal["en", "zh-TW"]


class SpeechToTextProvider(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        progress: ProgressCallback | None = None,
    ) -> Transcript: ...


class TranslationProvider(Protocol):
    def translate(self, transcript: Transcript) -> TranslatedTranscript: ...


class SummaryProvider(Protocol):
    def summarize(
        self,
        transcript: Transcript,
        language: SummaryLanguage,
    ) -> Summary: ...


SpeechProviderFactory = Callable[[WhisperProfile], SpeechToTextProvider]
TranslationProviderFactory = Callable[[], TranslationProvider]
SummaryProviderFactory = Callable[[], SummaryProvider]


@dataclass(frozen=True)
class LocalProviders:
    speech_to_text: SpeechToTextProvider
    translation: TranslationProvider
    summary: SummaryProvider


@dataclass(frozen=True)
class LocalProviderFactories:
    """Construct only Phase 1 local capabilities, each behind its own factory."""

    speech_to_text: SpeechProviderFactory
    translation: TranslationProviderFactory
    summary: SummaryProviderFactory

    def create(self, profile: WhisperProfile) -> LocalProviders:
        return LocalProviders(
            speech_to_text=self.speech_to_text(profile),
            translation=self.translation(),
            summary=self.summary(),
        )
