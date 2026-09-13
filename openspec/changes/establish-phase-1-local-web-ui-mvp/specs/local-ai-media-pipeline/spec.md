## Purpose

Defines the local, timestamp-preserving processing contract that converts supported media into English speech, Traditional Chinese text, and bilingual summaries without paid APIs.

## ADDED Requirements

### Requirement: Media audio is prepared locally
The system SHALL inspect supported media and extract or normalize audio into a format accepted by the configured Local Whisper model without passing media to a remote service.

#### Scenario: Prepare YouTube or MP4 audio
- **WHEN** a valid YouTube or MP4 source enters processing
- **THEN** the system extracts a local audio stream and advances the job to transcription

#### Scenario: Prepare MP3 audio
- **WHEN** a valid MP3 source enters processing
- **THEN** the system validates and converts it only as needed before transcription

#### Scenario: Media dependency is unavailable
- **WHEN** the required media inspection or conversion dependency is missing or cannot process the source
- **THEN** the job fails with setup or media guidance and does not expose a raw subprocess error to the user

### Requirement: Local Whisper produces timestamped English segments
The system SHALL use Local Whisper as the Phase 1 speech-to-text provider and SHALL represent every transcript segment with a stable segment identifier, start time, end time, source text, and English language code.

#### Scenario: Transcribe understandable speech
- **WHEN** prepared audio contains speech that Local Whisper can recognize
- **THEN** the system produces ordered English segments whose start times are non-negative and whose end times are not earlier than their start times

#### Scenario: Select a Whisper performance profile
- **WHEN** a user selects Fast, Balanced, or Accurate
- **THEN** the system maps that understandable profile to a documented local model configuration and uses it for the job

#### Scenario: Whisper model is unavailable
- **WHEN** the selected local model cannot be loaded or the computer lacks a required runtime dependency
- **THEN** the job fails with local setup guidance and without suggesting that a paid API is required

### Requirement: Long-media timestamps remain globally correct
The system SHALL support processing media in bounded chunks when required and MUST merge results into one chronologically ordered transcript using timestamps relative to the original media.

#### Scenario: Merge chunked transcription
- **WHEN** media is transcribed in two or more chunks
- **THEN** segment offsets are applied so that merged timestamps remain monotonic and point to the correct positions in the original media

### Requirement: Traditional Chinese translation preserves segment identity
The system SHALL translate each English segment into Traditional Chinese (`zh-TW`) through the configured Ollama-compatible local translation provider while retaining the original segment identifier and timestamps.

#### Scenario: Translate a transcript
- **WHEN** English transcript segments are available and the local translation provider responds successfully
- **THEN** each source segment has a corresponding Traditional Chinese translation with unchanged start and end times

#### Scenario: Translation response is incomplete
- **WHEN** the provider omits, duplicates, reorders, or returns an empty translation for a segment
- **THEN** the system detects the contract violation and fails the job instead of silently producing misaligned subtitles

### Requirement: Local summaries are generated in both languages
The system SHALL use an Ollama-compatible local summary provider to generate one English summary and one Traditional Chinese summary from the completed transcript without requiring timestamp citations in Phase 1.

#### Scenario: Generate bilingual summaries
- **WHEN** transcription and translation have completed and the local summary provider responds successfully
- **THEN** the job contains a non-empty English summary and a non-empty Traditional Chinese summary

#### Scenario: Local language model is unavailable
- **WHEN** the configured Ollama-compatible endpoint or model cannot be reached or used
- **THEN** the job fails with guidance that identifies the local translation or summary dependency without exposing internal secrets or stack traces

### Requirement: Capability providers remain independently replaceable
Speech-to-text, translation, and summary capabilities MUST have separate provider contracts, and the Phase 1 configuration SHALL select only Local Whisper and Ollama-compatible local implementations.

#### Scenario: Run without cloud credentials
- **WHEN** a user processes supported media with the documented local prerequisites installed
- **THEN** all required Phase 1 outputs can be generated without purchasing an API or entering a cloud API key
