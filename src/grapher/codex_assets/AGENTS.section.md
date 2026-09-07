<!-- grapher:codex:start -->
## grapher

This project uses **Grapher** for durable agent knowledge. `.grapher/knowledge.json` is local runtime state; Git-shared knowledge lives under `.grapher/shared/`.

**Codex session start:** if `.grapher/GRAPHER_CONTEXT.md` exists, read it completely before acting. That file is rendered from Grapher's model-agnostic agent contract and defines the required operating sequence: **READ → SEARCH → ACT → RECORD → VALIDATE → PUBLISH**.

After pulling repository changes, hydrate shared knowledge before work:

```bash
grapher sync
grapher search "<question>"
grapher get <id>
grapher neighbors <id> --depth 2
```

Rules:

- Search Grapher before rediscovering project state; do not treat recency as truth.
- Keep active context compact and retrieve only relevant slices.
- Repository files are implementation source; Grapher is durable semantic/project state.
- Deep understanding of documents, images, video, and audio belongs in node `content`; paths alone are not knowledge.
- Use explicit truth status, verification, scope, and provenance when recording durable state.
- Do not rewrite finalized history; use curation/supersession paths.
- Do not consolidate state across mission or generation boundaries.
- For semantic types, obey the exact JSON contracts in `docs/SEMANTIC_ENTRY_SCHEMA.md`.
- Before publication run `grapher validate`, `grapher audit`, and `grapher publish`.
- Commit `.grapher/shared/`; do not commit local runtime graph/vector/history files.
- After another agent publishes shared state, run `grapher sync` before relying on local knowledge.
- To transplant: `grapher codex export ./kit/` then elsewhere `grapher codex receive ./kit/`.
<!-- grapher:codex:end -->
