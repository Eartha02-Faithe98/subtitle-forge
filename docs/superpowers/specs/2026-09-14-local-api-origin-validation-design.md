# Local API Origin Validation Design

## Purpose

Prevent a page hosted on an untrusted origin from creating Subtitle Forge jobs in
the local FastAPI service. CORS response headers alone do not prevent a browser
from sending a simple cross-origin form POST, so job creation needs an explicit
request-origin check before it creates storage, persists a record, or enqueues
work.

## Scope

This change applies only to `POST /api/jobs`. It does not add authentication,
accounts, cloud endpoints, CSRF tokens, or changes to the local-only deployment
model.

## Decision

The job-creation route accepts a request without an `Origin` header so local
command-line and automated clients continue to work. If an `Origin` header is
present, the route accepts it only when it is an exact member of the validated
`SUBTITLE_FORGE_ALLOWED_ORIGINS` setting. An absent, malformed, or unlisted
origin is rejected with a safe `403 Forbidden` response before any job side
effect.

The settings validator remains the single authority for the allowlist: each
origin must be a credential-free HTTP(S) origin with no query, fragment, or
non-root path, and wildcard origins are forbidden.

## Request Flow

1. The route reads the optional `Origin` request header.
2. If it is absent, processing continues for local CLI compatibility.
3. If it is present, it is parsed as an origin and compared to the configured
   allowlist after normalization of a trailing slash.
4. A malformed or unlisted origin receives `403` and the route does not create
   a job directory, write a database row, read an upload, or enqueue work.
5. A configured browser origin continues through the existing source validation
   and processing flow unchanged.

## Error Handling

The rejection response uses a fixed, non-sensitive message. It does not echo
the supplied origin, upload name, path, URL, or configuration values.

## Tests

The API tests will prove that:

- an allowed browser origin can create a job;
- an unlisted origin receives `403` before storage or queue side effects;
- malformed origins receive the same safe `403` response;
- an origin-less local client preserves existing job-creation behavior.

## Non-goals and Residual Risk

This is browser-origin protection, not authentication. A program running under
the same local user can still call the local API directly; that program already
has equivalent access to the user's local media and process resources. The
service remains intended to bind to loopback by default. Users who deliberately
expose it beyond loopback need a separate authenticated deployment design.
