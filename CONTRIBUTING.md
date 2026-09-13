# Contributing to Subtitle Forge

Thank you for helping build Subtitle Forge as an open-source, local-first AI bilingual media knowledge tool.

## Current scope

Development is incremental. The current implementation is Phase 0: the local Next.js UI shell, FastAPI health contract, configuration baseline, and verification tooling. Do not present Phase 1 media or AI capabilities as available until their own specifications and acceptance criteria pass.

Read [CODEX_DEVELOPMENT_SPEC.md](CODEX_DEVELOPMENT_SPEC.md) and the active OpenSpec change before making architecture or behavior changes.

## Local setup

Use Windows 11, Python 3.11 or newer, Node.js 20.9 or newer, npm, and Google Chrome. Follow the complete commands in [README.md](README.md#development-setup).

## Before submitting a change

Run the full Phase 0 verification command from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

The command checks backend formatting, linting, types, and tests; frontend formatting, linting, types, tests, and build; and the real browser-to-backend smoke test.

Keep changes small and add a failing test before implementing new behavior. Update OpenSpec artifacts and README claims when externally observable behavior changes.

## Secret handling

- Never commit `.env`, API keys, access tokens, passwords, private media, or generated user data.
- Add only placeholders or non-sensitive local defaults to `.env.example`.
- Keep future provider credentials in backend-only configuration or a credential-store abstraction.
- Never print secrets in logs, browser output, HTTP errors, test snapshots, or issue reports.

## Pull request notes

Describe the user-visible behavior, tests run, known limitations, and the OpenSpec capability affected. Verify that no generated dependencies, caches, runtime logs, browser traces, or local environment files are included.

By contributing, you agree that your contribution is licensed under the [MIT License](LICENSE).
