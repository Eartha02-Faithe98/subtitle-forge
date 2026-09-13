# Codex Development Specification

## Project: Subtitle Forge

**Repository:** `subtitle-forge`\
**Project Type:** Open Source AI Bilingual Media Knowledge Tool\
**Primary Development Environment:** Windows 11\
**Phase 1 Deployment:** Local Web UI\
**Future Direction:** Web App / SaaS

------------------------------------------------------------------------

# 1. Product Vision

Subtitle Forge is an open-source AI media processing and knowledge tool.

Its purpose is not merely to generate subtitles.

The long-term product workflow is:

Video / Audio / URL → Media Extraction → Speech-to-Text → English
Transcript → Traditional Chinese Translation → Bilingual Subtitles →
Summary / Chapters / Key Points → Searchable Knowledge → Timestamp-Cited
AI Q&A

The product should eventually transform:

**Media → Subtitles → Transcript → Knowledge**

The system must be designed so that the initial Local Web UI can later
evolve into a multi-user Web App / SaaS without requiring a complete
rewrite.

------------------------------------------------------------------------

# 2. Product Positioning

Do NOT position the product merely as:

> AI Subtitle Generator

Preferred positioning:

> AI Bilingual Media Knowledge Tool

or:

> Media → Knowledge

Potential tagline:

> Turn any video or audio into bilingual subtitles and knowledge.

------------------------------------------------------------------------

# 3. Confirmed Product Decisions

  Item                             Decision
  -------------------------------- -------------------------------
  Repository                       `subtitle-forge`
  Open Source                      Yes
  Phase 1                          Local Web UI
  Future                           Web App / SaaS
  Primary OS                       Windows 11
  YouTube                          Required in MVP
  MP3                              Required in MVP
  MP4                              Required in MVP
  Website article URL              Phase 2
  Website video URL                Phase 2
  Chinese                          Traditional Chinese (`zh-TW`)
  Paid API                         Must NOT be mandatory
  Local AI                         Required / preferred
  BYO API Key                      Required
  Persistent API configuration     Required
  English SRT                      Required
  Traditional Chinese SRT          Required
  Bilingual SRT                    Required
  English Transcript               Required
  Traditional Chinese Transcript   Required
  English Summary                  Required
  Traditional Chinese Summary      Required
  Timestamp preservation           Required
  Future RAG                       Yes
  Future timestamp-cited Q&A       Yes
  Future SaaS                      Yes

------------------------------------------------------------------------

# 4. Core Principle: Local First, SaaS Later

Development roadmap:

**Phase 0 Foundation** → **Phase 1 Local Web UI MVP** → **Phase 2 More
Media Sources** → **Phase 3 Better Subtitle / Knowledge Features** →
**Phase 4 RAG + Timestamp Q&A** → **Phase 5 Web App Architecture** →
**Phase 6 Production SaaS**

Do NOT attempt to implement all phases simultaneously.

Each phase must be independently testable.

At the end of each phase:

1.  Run tests.
2.  Fix regressions.
3.  Update documentation.
4.  Update README.
5.  Verify previous features.
6.  Only then proceed.

------------------------------------------------------------------------

# 5. Phase 1 User Experience

Phase 1 is a **Local Web UI**.

The user opens:

`http://localhost:3000`

or another configured local port.

Normal media processing should not require CLI usage.

CLI commands may exist for development and administration.

------------------------------------------------------------------------

# 6. MVP User Workflow

1.  Start Subtitle Forge.
2.  Open the Local Web UI.
3.  Select YouTube URL / MP3 / MP4.
4.  Select STT provider.
5.  Select Translation provider.
6.  Select Summary provider.
7.  Start processing.
8.  Show processing progress.
9.  Generate:
    -   English transcript
    -   Traditional Chinese transcript
    -   English SRT
    -   Traditional Chinese SRT
    -   Bilingual SRT
    -   English summary
    -   Traditional Chinese summary
10. Allow the user to download generated files.

------------------------------------------------------------------------

# 7. AI Provider Architecture

Use **provider interfaces / adapters**.

The core application must depend on provider interfaces rather than
specific vendor implementations.

## Speech-to-Text Providers

Initial architecture should support:

-   Local Whisper
-   OpenAI
-   Groq
-   Other compatible providers in the future

## Translation Providers

Initial architecture should support:

-   Local LLM / Ollama
-   OpenAI
-   Google Gemini
-   Anthropic Claude
-   Groq
-   OpenAI-compatible APIs

## Summary Providers

Initial architecture should support:

-   Local LLM / Ollama
-   OpenAI
-   Google Gemini
-   Anthropic Claude
-   Groq
-   OpenAI-compatible APIs

Conceptual interfaces:

``` text
SpeechToTextProvider.transcribe(audio, options) -> Transcript

TranslationProvider.translate(
    text,
    source_language,
    target_language,
    options
) -> translated_text

SummaryProvider.summarize(
    transcript,
    options
) -> Summary
```

The application must allow a different provider for each capability.

------------------------------------------------------------------------

# 8. API Key Management

Subtitle Forge must support **BYO API Key**.

No paid API may be mandatory.

API keys should persist across application restarts.

Prefer OS-level secure credential storage where practical, such as
Windows Credential Manager or an equivalent secure-storage mechanism.

At minimum:

-   `.env` must be gitignored.
-   `.env.example` must be provided.
-   API keys must never be hard-coded.
-   API keys must never be committed to Git.
-   API keys must not be unnecessarily exposed to frontend JavaScript.
-   API keys must not appear in logs.

Use a credential abstraction such as:

``` text
CredentialStore
├── save(provider, key)
├── get(provider)
└── delete(provider)
```

The implementation may use a secure OS credential store or another
appropriate local mechanism.

------------------------------------------------------------------------

# 9. Speech-to-Text

Primary local STT implementation:

**Whisper**

The local Whisper implementation should be the primary free/local
option.

Expose configurable model levels such as:

-   Fast
-   Balanced
-   Accurate

Do not assume that every computer has the same hardware.

The UI should make model selection understandable without requiring
users to understand GPU/CPU details.

------------------------------------------------------------------------

# 10. Translation Providers

Translation must use the provider abstraction.

Local translation should be possible through an Ollama-compatible local
LLM.

Cloud providers may be selected when the user supplies their own API
key.

Target language for the MVP:

**Traditional Chinese (`zh-TW`)**

------------------------------------------------------------------------

# 11. Summary Providers

Summary generation must use the same provider abstraction philosophy.

The user should be able to choose a local or cloud provider.

Required MVP outputs:

-   English Summary
-   Traditional Chinese Summary

------------------------------------------------------------------------

# 12. Hybrid AI Mode

The system must support different providers for different capabilities.

Example:

``` text
STT:
    Local Whisper

Translation:
    Google Gemini

Summary:
    OpenAI
```

Another valid configuration:

``` text
STT:
    Groq

Translation:
    Local Ollama

Summary:
    Claude
```

Do not force the entire workflow to use one provider.

------------------------------------------------------------------------

# 13. API Key Security

Security requirements:

-   Never hard-code API keys.
-   Never commit API keys.
-   Never print API keys in logs.
-   Never include API keys in frontend source unnecessarily.
-   Never expose secrets in error messages.
-   Sanitize logs and diagnostic output.
-   Keep `.env` out of Git.
-   Provide `.env.example` without real credentials.

------------------------------------------------------------------------

# 14. Settings UI

Provide a Settings section.

Suggested structure:

``` text
Settings
├── AI Providers
│   ├── STT Provider
│   ├── Translation Provider
│   └── Summary Provider
│
├── API Keys
│   ├── OpenAI
│   ├── Gemini
│   ├── Anthropic
│   └── Groq
│
├── Local AI
│   ├── Whisper Model
│   └── Local LLM
│
└── General
```

Only implement settings required by the current development phase.

Do not build a complicated settings system prematurely.

------------------------------------------------------------------------

# 15. Input Sources --- Phase 1

Required MVP inputs:

1.  YouTube URL
2.  MP3 upload
3.  MP4 upload

The system must gracefully handle:

-   Invalid URLs
-   Private videos
-   Removed videos
-   Network errors
-   Unsupported media
-   Corrupted uploads
-   Oversized files
-   Missing dependencies

------------------------------------------------------------------------

# 16. FFmpeg

Use FFmpeg as the main media-processing layer.

Potential responsibilities:

-   Audio extraction
-   Audio conversion
-   Audio normalization
-   Media metadata inspection
-   Media splitting / chunking
-   Future subtitle burn-in

Use a media abstraction:

``` text
MediaService
├── probe()
├── extract_audio()
├── convert()
└── split()
```

Do not spread raw FFmpeg command construction throughout the
application.

------------------------------------------------------------------------

# 17. Long Media Processing

Architecture must support long media.

General pipeline:

``` text
Video
↓
Audio
↓
Chunks
↓
STT per chunk
↓
Merge transcripts
↓
Preserve timestamps
↓
Translation
↓
SRT generation
```

The system must not lose timestamp information when chunks are merged.

The MVP may begin with a simpler implementation if appropriate, but the
data model and service boundaries must not prevent later chunking.

------------------------------------------------------------------------

# 18. Transcript Data Model

Minimum transcript segment:

``` text
segment_id
start_time
end_time
source_text
language
```

Future fields may include:

``` text
speaker
translated_text
confidence
chapter_id
embedding_id
```

Use timestamps as first-class data.

------------------------------------------------------------------------

# 19. Timestamp Integrity

Timestamp preservation is a core requirement.

Timestamps should survive:

``` text
STT
→ Translation
→ Subtitle generation
→ Summary references
→ Future RAG
→ Future AI Q&A
```

For bilingual subtitles, the original transcript timestamps can normally
be reused:

``` text
001
00:01:10,000 --> 00:01:13,000
This is a very important concept.
這是一個非常重要的概念。
```

Do not regenerate timestamps after translation unless there is a clear
reason.

------------------------------------------------------------------------

# 20. Subtitle Generation

Required outputs:

-   English SRT
-   Traditional Chinese SRT
-   Bilingual SRT

Subtitle generation must be deterministic and testable.

Segmentation should consider:

-   Original timestamps
-   Sentence boundaries
-   Punctuation
-   Reading speed
-   Line length
-   Subtitle duration
-   Natural language readability

Do not blindly split subtitles based only on character count.

------------------------------------------------------------------------

# 21. Transcript Output

Generate:

-   English transcript
-   Traditional Chinese transcript

Both should retain timestamp information.

Recommended display:

``` text
[00:01:10]
This is a very important concept.

[00:01:10]
這是一個非常重要的概念。
```

------------------------------------------------------------------------

# 22. Summary Output

Generate:

-   English Summary
-   Traditional Chinese Summary

Future versions should allow summary items to reference timestamps.

Example:

``` text
## Key Point

The speaker explains why stateless services simplify horizontal scaling.

Timestamp:
32:15
```

------------------------------------------------------------------------

# 23. Recommended Project Structure

Suggested initial structure:

``` text
subtitle-forge/
├── frontend/
├── backend/
├── services/
│   ├── media/
│   ├── transcription/
│   ├── translation/
│   ├── summary/
│   ├── subtitles/
│   └── providers/
├── tests/
├── docs/
├── scripts/
├── .env.example
├── .gitignore
├── README.md
├── LICENSE
└── CODEX_DEVELOPMENT_SPEC.md
```

The exact structure may be adjusted by Codex if there is a strong
technical reason.

Avoid needless complexity.

------------------------------------------------------------------------

# 24. Recommended Technology Stack

## Frontend

-   React
-   Next.js
-   TypeScript

## Backend

-   Python
-   FastAPI

## Media

-   FFmpeg

## Speech-to-Text

-   Whisper

## Local LLM

-   Ollama-compatible architecture

## Database

MVP:

-   SQLite

Future:

-   PostgreSQL

## Vector Database

Future:

-   pgvector

## Background Jobs

MVP:

-   Simple local job handling

Future:

-   Queue + workers

Do not introduce Redis, distributed queues, microservices, or Kubernetes
in the MVP unless there is a concrete requirement.

------------------------------------------------------------------------

# 25. Local MVP Architecture

``` text
Browser
   ↓
Local Web UI
   ↓
React / Next.js
   ↓
FastAPI
   ↓
┌─────────────────────────────────┐
│ Media Service                   │
│ Transcription Service           │
│ Translation Service             │
│ Summary Service                 │
│ Subtitle Service                │
│ Provider Adapters               │
└─────────────────────────────────┘
   ↓
┌─────────────────────────────────┐
│ FFmpeg                          │
│ Whisper                         │
│ Local LLM                       │
│ Cloud AI APIs                   │
└─────────────────────────────────┘
```

------------------------------------------------------------------------

# 26. Future SaaS Architecture

``` text
Users
   ↓
Web App
   ↓
API
   ↓
Authentication
   ↓
Job Queue
   ↓
Workers
   ↓
┌─────────────────────────────┐
│ Database                    │
│ Object Storage              │
│ AI Providers                │
└─────────────────────────────┘
```

The Local MVP should not implement this entire architecture.

It should merely avoid architectural decisions that make future
migration unnecessarily difficult.

------------------------------------------------------------------------

# 27. Phase 0 --- Foundation

## Goal

Create a clean, runnable project foundation.

## Tasks

-   Initialize repository.
-   Create frontend.
-   Create backend.
-   Establish frontend/backend communication.
-   Create configuration system.
-   Create `.env.example`.
-   Create `.gitignore`.
-   Create README.
-   Add open-source license.
-   Add tests.
-   Add health endpoint.
-   Create basic UI shell.

## Acceptance Criteria

-   Application starts successfully.
-   Frontend loads.
-   Backend loads.
-   Frontend can communicate with backend.
-   Health endpoint works.
-   No secrets are committed.
-   Tests pass.

------------------------------------------------------------------------

# 28. Phase 1 --- Local Web UI MVP

## Goal

Create a useful end-to-end workflow.

## Inputs

-   YouTube URL
-   MP3
-   MP4

## Required Capabilities

-   Local Whisper
-   Provider abstraction
-   Optional cloud providers
-   Traditional Chinese translation
-   Summary generation
-   Subtitle generation

## Outputs

-   English Transcript
-   Traditional Chinese Transcript
-   English SRT
-   Traditional Chinese SRT
-   Bilingual SRT
-   English Summary
-   Traditional Chinese Summary

## UI

``` text
Home
 ↓
YouTube URL / Upload
 ↓
STT Provider
 ↓
Translation Provider
 ↓
Summary Provider
 ↓
Start Processing
```

## Progress

``` text
Downloading
 ↓
Extracting Audio
 ↓
Transcribing
 ↓
Translating
 ↓
Generating Subtitles
 ↓
Generating Summary
 ↓
Completed
```

## Acceptance Criteria

A Windows 11 user can:

1.  Start Subtitle Forge.
2.  Open the Local Web UI.
3.  Provide a YouTube URL or MP3/MP4.
4.  Select providers.
5.  Start processing.
6.  See processing progress.
7.  Obtain all required outputs.
8.  Download the outputs.

A paid API purchase must not be required when the user uses supported
local AI components.

------------------------------------------------------------------------

# 29. Phase 2 --- Website URL

Support two categories.

## A. Article URL

``` text
URL
↓
Article Extraction
↓
Text
↓
Translation
↓
Summary
```

## B. Webpage Containing Video

``` text
URL
↓
Detect Media
↓
Extract Media
↓
Speech-to-Text
↓
Translation
↓
SRT
```

Possible additional features:

-   VTT
-   Subtitle editor
-   Speaker detection
-   Chapters
-   Key points
-   Transcript search
-   Subtitle burn-in
-   Batch processing
-   ZIP export

Prioritize reliability over feature count.

------------------------------------------------------------------------

# 30. Phase 3 --- Knowledge Layer

Build a project-based knowledge library:

``` text
Project
├── Media
├── Transcript
├── Subtitles
├── Summary
├── Chapters
├── Key Points
└── Search
```

The goal is to transform generated transcripts into reusable knowledge
rather than one-time subtitle files.

------------------------------------------------------------------------

# 31. Phase 4 --- RAG + Timestamp-Cited AI Q&A

Future workflow:

``` text
User Question
↓
Retrieval
↓
Relevant Transcript Segments
↓
LLM
↓
Answer + Timestamp Citations
```

Example:

``` text
Q:
Why does the speaker recommend a stateless architecture?

A:
Because stateless services make horizontal scaling easier by
avoiding server-local session state.

Source:
32:15
```

The UI should eventually allow:

> Jump to 32:15

The timestamp should point back to the original media.

------------------------------------------------------------------------

# 32. RAG Architecture

Future RAG pipeline:

``` text
Transcript
↓
Chunking
↓
Embeddings
↓
pgvector
↓
Semantic Search
↓
Relevant Transcript Segments
↓
LLM
↓
Answer + Timestamp Citations
```

Each retrieved segment should preserve:

``` text
project_id
segment_id
start_time
end_time
source_text
```

Do not detach semantic chunks from their original timestamps.

------------------------------------------------------------------------

# 33. Future Technical Video Mode

A future Technical Video Mode may extract:

-   Technical terms
-   Concepts
-   Commands
-   Code
-   APIs
-   Architecture
-   Tools
-   Frameworks
-   Definitions

Example:

``` text
Term:
Load Balancer

Explanation:
A component that distributes incoming traffic across
multiple server instances.

Source:
18:42
```

This is a future feature and should not be implemented during MVP unless
specifically requested.

------------------------------------------------------------------------

# 34. Future English Learning Mode

Potential workflow:

``` text
English Transcript
↓
Traditional Chinese Translation
↓
Vocabulary
↓
Phrases
↓
Listening / Pronunciation
↓
Shadowing
↓
Quiz
```

This is a future feature.

Do not implement it during MVP.

------------------------------------------------------------------------

# 35. Future SaaS Requirements

Eventually support:

-   User registration
-   Login
-   Password reset
-   OAuth where appropriate
-   User accounts
-   Projects
-   Usage tracking
-   Plans
-   Credits
-   Billing
-   Subscriptions

Do not implement billing or subscriptions in the MVP.

------------------------------------------------------------------------

# 36. Future SaaS Data Model

Potential entities:

``` text
User
Project
Asset
Job
Transcript
TranscriptSegment
Subtitle
Summary
Chapter
Usage
Subscription
CredentialReference
Embedding
```

The exact schema should evolve as requirements become concrete.

------------------------------------------------------------------------

# 37. Background Job Architecture

## MVP

``` text
POST /process
↓
Create Job
↓
Process
↓
Update Job Status
```

## Future SaaS

``` text
API
↓
Queue
↓
Worker
↓
Job
```

The MVP should keep the implementation simple while maintaining explicit
job boundaries.

------------------------------------------------------------------------

# 38. Job State Machine

Recommended states:

``` text
PENDING
DOWNLOADING
EXTRACTING_AUDIO
TRANSCRIBING
TRANSLATING
GENERATING_SUBTITLES
GENERATING_SUMMARY
COMPLETED
FAILED
CANCELLED
```

State transitions must be explicit and testable.

------------------------------------------------------------------------

# 39. Error Handling

User-facing errors should be understandable.

Example:

Bad:

``` text
subprocess returned exit code 1
```

Better:

``` text
Unable to extract audio from this video.
Please verify that the URL is accessible and try again.
```

Technical details should be retained in logs for debugging.

------------------------------------------------------------------------

# 40. Logging

Use structured logging where practical.

Useful fields:

``` text
job_id
project_id
stage
provider
duration
error
```

Never log:

-   API keys
-   Access tokens
-   Passwords
-   Other credentials

------------------------------------------------------------------------

# 41. Configuration

Use environment variables for application-level configuration.

Provider configuration should not require source-code modification.

Example:

``` text
OPENAI_API_KEY
GEMINI_API_KEY
ANTHROPIC_API_KEY
GROQ_API_KEY
```

However, user-entered credentials should preferably be stored through
the secure credential abstraction rather than requiring manual editing
of `.env`.

------------------------------------------------------------------------

# 42. Testing

## Unit Tests

At minimum:

-   Subtitle generation
-   Timestamp formatting
-   Translation adapter behavior
-   Provider selection
-   Configuration
-   Job transitions
-   Media validation

## Integration Tests

Test:

``` text
Input
↓
Processing
↓
Transcript
↓
Translation
↓
SRT
```

## Regression Testing

Previous features must remain functional when new phases are added.

------------------------------------------------------------------------

# 43. Security

The application must:

-   Never commit API keys.
-   Validate uploaded files.
-   Restrict supported file types.
-   Restrict upload sizes where appropriate.
-   Validate URLs.
-   Avoid command injection.
-   Never construct unsafe shell commands from untrusted input.
-   Sanitize filenames.
-   Prevent path traversal.
-   Manage temporary files safely.
-   Clean up temporary files after processing.
-   Avoid exposing internal filesystem paths unnecessarily.

------------------------------------------------------------------------

# 44. Open Source Requirements

Repository should contain:

``` text
README.md
LICENSE
CONTRIBUTING.md
.env.example
.gitignore
CODEX_DEVELOPMENT_SPEC.md
```

Later:

``` text
CHANGELOG.md
SECURITY.md
CODE_OF_CONDUCT.md
```

------------------------------------------------------------------------

# 45. README Requirements

README must explain:

-   What is Subtitle Forge?
-   Product positioning
-   Available features
-   Planned features
-   Windows 11 installation
-   How to run
-   AI providers
-   Local AI
-   BYO API Key
-   Security considerations
-   Roadmap
-   Development setup

Never claim unfinished features as complete.

------------------------------------------------------------------------

# 46. Development Philosophy

Do not over-engineer the MVP.

Avoid:

-   Kubernetes
-   Microservices
-   Distributed queues
-   Complex orchestration
-   Enterprise permissions
-   Multi-region infrastructure

unless a concrete requirement makes them necessary.

At the same time:

-   Avoid one giant monolithic module.
-   Provider abstraction is mandatory.
-   Storage abstraction is preferred.
-   Database abstraction is preferred.
-   Keep services independently testable.

------------------------------------------------------------------------

# 47. Do Not Implement Future Features Early

Do NOT implement these during MVP:

-   Billing
-   Subscriptions
-   Multi-user authentication
-   Teams
-   Complex RAG
-   Vector database
-   Kubernetes
-   Distributed workers
-   Enterprise permissions

The architecture should not prevent these features later.

------------------------------------------------------------------------

# 48. Phase Completion Rule

At the end of every phase, report:

``` text
Phase:
Status:
Implemented:
Tests:
Known Issues:
Files Changed:
How to Run:
Acceptance Criteria:
    PASS / FAIL
```

If acceptance criteria fail, do not claim the phase is complete.

------------------------------------------------------------------------

# 49. Definition of Done

A feature is considered done only when:

``` text
Code implemented
+
Tests passing
+
Error handling
+
Documentation
+
UI usable
+
Acceptance criteria satisfied
```

------------------------------------------------------------------------

# 50. MVP Definition of Done

A Windows 11 user can:

``` text
Start Subtitle Forge
↓
Open Local Web UI
↓
YouTube / MP3 / MP4
↓
Local Whisper
↓
English Transcript
↓
Traditional Chinese Translation
↓
English SRT
↓
Traditional Chinese SRT
↓
Bilingual SRT
↓
English Summary
↓
Traditional Chinese Summary
↓
Download Outputs
```

No paid API purchase is required when supported local AI components can
run on the user's computer.

------------------------------------------------------------------------

# 51. Long-Term Architecture

``` text
Subtitle Forge
│
├── Local Mode
│   ├── Local Web UI
│   ├── Whisper
│   ├── Local LLM
│   └── Local Files
│
└── Cloud Mode
    ├── Web App
    ├── API
    ├── Workers
    ├── Storage
    ├── PostgreSQL
    ├── pgvector
    └── AI Providers
```

Share core business logic between Local and Cloud modes where practical.

------------------------------------------------------------------------

# 52. Product Differentiation

Do not compete only on:

``` text
Upload → Subtitle
```

Long-term product differentiation should focus on:

``` text
Video / Audio
↓
Bilingual Transcript
↓
Timestamped Knowledge
↓
Search
↓
Summary
↓
Chapters
↓
AI Q&A
↓
Timestamp Evidence
```

The primary differentiator should be:

> AI answers that cite exactly where the information appears in the
> original media.

This turns Subtitle Forge from a simple subtitle generator into a
**media-to-knowledge tool**.

------------------------------------------------------------------------

# 53. Development Priorities

When choosing between implementation options, prioritize in this order:

1.  Correctness
2.  Timestamp integrity
3.  Local-first usability
4.  Provider modularity
5.  Security
6.  Testability
7.  Reliability
8.  Simplicity
9.  Future SaaS compatibility
10. Additional features

Do not sacrifice core reliability merely to increase feature count.

------------------------------------------------------------------------

# 54. Codex Development Workflow

Codex should work incrementally.

For each phase:

``` text
Understand requirements
↓
Inspect current repository
↓
Plan implementation
↓
Implement small increments
↓
Run tests
↓
Fix failures
↓
Run application
↓
Verify acceptance criteria
↓
Update documentation
↓
Report results
```

Codex should not attempt to build the entire product in a single pass.

------------------------------------------------------------------------

# 55. Assumption Handling

When requirements are ambiguous:

1.  Prefer the simplest implementation.
2.  Prefer local-first behavior.
3.  Prefer open-source solutions.
4.  Avoid mandatory paid APIs.
5.  Keep providers modular.
6.  Preserve timestamps.
7.  Preserve security.
8.  Preserve testability.
9.  Avoid premature infrastructure.
10. Document important assumptions.

Do not invent major product requirements without documenting the
assumption.

------------------------------------------------------------------------

# 56. Final Instruction to Codex

Treat this document as the product development specification for
Subtitle Forge.

Do not build the entire product in one pass.

Start with **Phase 0**.

After Phase 0 passes its acceptance criteria, proceed to **Phase 1**.

Only proceed to later phases after the previous phase has been tested
and verified.

When ambiguous, prefer:

1.  Simple
2.  Local-first
3.  Open-source
4.  No mandatory paid API
5.  Modular providers
6.  Security
7.  Testability
8.  Future SaaS compatibility

Do not:

-   Hard-code providers.
-   Hard-code API keys.
-   Commit secrets.
-   Lose timestamps.
-   Claim incomplete features are complete.
-   Introduce unnecessary infrastructure.
-   Implement future SaaS complexity before it is needed.

The ultimate goal is:

> **Subtitle Forge --- an open-source AI Bilingual Media Knowledge Tool
> that transforms video and audio into bilingual subtitles, transcripts,
> summaries, and eventually timestamp-cited searchable knowledge.**

------------------------------------------------------------------------

# 57. Immediate First Task for Codex

When this specification is first given to Codex, the immediate task is:

> **Implement Phase 0 only.**

Before writing substantial code:

1.  Inspect the repository.
2.  Identify existing files and tooling.
3.  Confirm whether the repository is empty or already initialized.
4.  Create a minimal implementation plan.
5.  Implement Phase 0.
6.  Run tests.
7.  Start the application if possible.
8.  Verify frontend/backend communication.
9.  Verify the health endpoint.
10. Verify that no secrets are committed.
11. Update README.
12. Report the Phase 0 completion status.

Do not begin Phase 1 until Phase 0 acceptance criteria pass.

------------------------------------------------------------------------

# End of Specification
