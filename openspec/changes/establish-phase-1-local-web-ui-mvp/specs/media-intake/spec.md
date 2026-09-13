## Purpose

Defines the supported Phase 1 media sources and the validation and containment rules that make local intake safe and predictable.

## ADDED Requirements

### Requirement: Exactly one supported source per job
The system SHALL accept exactly one source for each processing job: a YouTube URL, an MP3 upload, or an MP4 upload.

#### Scenario: Submit a supported source
- **WHEN** a user submits one valid YouTube URL, MP3 file, or MP4 file
- **THEN** the system accepts the source and creates one processing job

#### Scenario: Submit no source or multiple sources
- **WHEN** a request contains no source or more than one source
- **THEN** the system rejects the request with a message asking the user to choose exactly one source

### Requirement: YouTube intake is constrained
The system SHALL accept valid HTTP or HTTPS YouTube watch or short URLs and MUST reject malformed, non-YouTube, private, removed, or otherwise inaccessible videos with an actionable user-facing error.

#### Scenario: Submit a public YouTube video
- **WHEN** a user submits a syntactically valid URL for an accessible public YouTube video
- **THEN** the system acquires the media for local processing without requiring the user to download it manually

#### Scenario: Submit an inaccessible YouTube video
- **WHEN** the submitted YouTube video is private, removed, unavailable, or cannot be downloaded because of a network failure
- **THEN** the job fails safely and tells the user that the video could not be accessed or downloaded

#### Scenario: Submit a non-YouTube URL
- **WHEN** a user submits an article URL, arbitrary website URL, or unsupported video host
- **THEN** the system rejects it before processing and identifies YouTube as the only Phase 1 URL source

### Requirement: Uploaded media is validated
The system MUST enforce configurable upload size limits and SHALL validate uploaded MP3 and MP4 media from their content rather than trusting only the filename extension or browser content type.

#### Scenario: Upload valid media
- **WHEN** an MP3 or MP4 is within the configured size limit and its content is readable as the declared media type
- **THEN** the system accepts the upload for processing

#### Scenario: Upload unsupported, corrupt, or oversized content
- **WHEN** an upload is not valid MP3 or MP4 media, is corrupted, or exceeds the configured limit
- **THEN** the system rejects it without processing and explains whether the type, integrity, or size caused the rejection

### Requirement: Intake cannot escape managed storage
The system MUST sanitize untrusted filenames and identifiers, MUST prevent path traversal and command injection, and MUST keep acquired and uploaded media inside an ignored application-managed data area.

#### Scenario: Upload a hostile filename
- **WHEN** an uploaded filename contains path components, shell metacharacters, reserved names, or control characters
- **THEN** the system stores the content under a generated safe name and does not interpret the supplied name as a path or command

#### Scenario: Intake processing finishes
- **WHEN** source acquisition or validation reaches completion or failure
- **THEN** disposable intake files are removed according to the documented cleanup policy while retained job artifacts remain downloadable
