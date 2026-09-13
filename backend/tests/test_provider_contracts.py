from pathlib import Path
from typing import Literal

from subtitle_forge_api.domain import (
    Summary,
    Transcript,
    TranscriptSegment,
    TranslatedSegment,
    TranslatedTranscript,
    WhisperProfile,
)
from subtitle_forge_api.providers import LocalProviderFactories


def english_transcript() -> Transcript:
    return Transcript(
        segments=(
            TranscriptSegment(
                segment_id="segment-000001",
                start_ms=0,
                end_ms=1_000,
                source_text="Hello local providers.",
            ),
        )
    )


class FakeSpeechProvider:
    def __init__(self, label: str) -> None:
        self.label = label

    def transcribe(
        self,
        audio_path: Path,
        progress: object | None = None,
    ) -> Transcript:
        del audio_path, progress
        return english_transcript()


class FakeTranslationProvider:
    def translate(self, transcript: Transcript) -> TranslatedTranscript:
        source = transcript.segments[0]
        return TranslatedTranscript(
            segments=(
                TranslatedSegment(
                    segment_id=source.segment_id,
                    start_ms=source.start_ms,
                    end_ms=source.end_ms,
                    translated_text="您好，本機供應者。",
                ),
            )
        )


class FakeSummaryProvider:
    def summarize(
        self,
        transcript: Transcript,
        language: Literal["en", "zh-TW"],
    ) -> Summary:
        del transcript
        return Summary(language=language, text=f"{language} summary")


def test_local_factories_create_three_independently_replaceable_capabilities() -> None:
    requested_profiles: list[WhisperProfile] = []
    translation_instances: list[FakeTranslationProvider] = []
    summary_instances: list[FakeSummaryProvider] = []

    def speech_factory(profile: WhisperProfile) -> FakeSpeechProvider:
        requested_profiles.append(profile)
        return FakeSpeechProvider(profile.value)

    def translation_factory() -> FakeTranslationProvider:
        provider = FakeTranslationProvider()
        translation_instances.append(provider)
        return provider

    def summary_factory() -> FakeSummaryProvider:
        provider = FakeSummaryProvider()
        summary_instances.append(provider)
        return provider

    providers = LocalProviderFactories(
        speech_to_text=speech_factory,
        translation=translation_factory,
        summary=summary_factory,
    ).create(WhisperProfile.BALANCED)

    assert providers.speech_to_text.label == "balanced"
    assert providers.translation is translation_instances[0]
    assert providers.summary is summary_instances[0]
    assert requested_profiles == [WhisperProfile.BALANCED]


def test_replacing_translation_does_not_replace_speech_or_summary() -> None:
    speech = FakeSpeechProvider("local-whisper")
    summary = FakeSummaryProvider()
    first_translation = FakeTranslationProvider()
    second_translation = FakeTranslationProvider()

    first = LocalProviderFactories(
        speech_to_text=lambda profile: speech,
        translation=lambda: first_translation,
        summary=lambda: summary,
    ).create(WhisperProfile.FAST)
    second = LocalProviderFactories(
        speech_to_text=lambda profile: speech,
        translation=lambda: second_translation,
        summary=lambda: summary,
    ).create(WhisperProfile.FAST)

    assert first.speech_to_text is second.speech_to_text
    assert first.summary is second.summary
    assert first.translation is not second.translation


def test_contracts_return_canonical_domain_models() -> None:
    providers = LocalProviderFactories(
        speech_to_text=lambda profile: FakeSpeechProvider(profile.value),
        translation=FakeTranslationProvider,
        summary=FakeSummaryProvider,
    ).create(WhisperProfile.ACCURATE)

    transcript = providers.speech_to_text.transcribe(Path("prepared.wav"))
    translated = providers.translation.translate(transcript)
    summary = providers.summary.summarize(transcript, "zh-TW")

    assert isinstance(transcript, Transcript)
    assert translated.segments[0].segment_id == transcript.segments[0].segment_id
    assert summary.language == "zh-TW"
