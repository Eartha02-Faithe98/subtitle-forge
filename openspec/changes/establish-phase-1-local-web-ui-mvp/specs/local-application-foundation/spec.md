## ADDED Requirements

### Requirement: Phase-aware local application shell
The frontend SHALL render a usable Subtitle Forge application shell that identifies the product as an AI bilingual media knowledge tool, presents implemented Phase 1 capabilities truthfully, and distinguishes later roadmap features from available behavior.

#### Scenario: Open the Phase 1 Local Web UI
- **WHEN** a user opens the running frontend in a supported modern browser
- **THEN** the page identifies Subtitle Forge, presents the available Phase 1 local media workflow, and does not claim that Phase 2, knowledge-layer, RAG, account, billing, or SaaS features are available

## REMOVED Requirements

### Requirement: Phase 0 UI shell
**Reason**: The foundation-only page is superseded by the implemented Phase 1 media workflow after Phase 0 passed its acceptance criteria.

**Migration**: Preserve the product identity, backend connectivity state, responsive behavior, and truthful roadmap labeling inside the Phase 1 application shell.
