<!-- grapher:codex:start -->
## grapher

This project uses **grapher** for shared agent knowledge (`.grapher/knowledge.json`).

**On session start / when using a transplanted idea:** if `.grapher/GRAPHER_CONTEXT.md` exists, **read that entire file first** before exploring or re-deriving. It is the full-fidelity transplant of the idea (every node’s deep content + relationships).

Then use the CLI:

```bash
grapher search "<question>"
grapher get <id>
grapher neighbors <id> --depth 2
```

Rules:

- Prefer grapher search/get over rediscovering known context.
- Deep understanding of documents, images, video, and audio lives in node `content` — **paths alone are not knowledge**.
- For semantic types (`observation`, `problem`, `question`, `hypothesis`, `requirement`, `constraint`, `proposal`, `decision`, `task`, `implementation`, `test`, `result`, `failure`, `lesson`), write `--content` as the required JSON object documented in `docs/SEMANTIC_ENTRY_SCHEMA.md`; free-form semantic filler is rejected.
- Temporary empty semantic stubs are allowed while unclassified/unverified, but current, canonical, verified, or finalized semantic records must be complete.
- After discoveries: `grapher add` / `grapher link` with dense, grounded content and precise relations.
- To transplant: `grapher codex export ./kit/` then elsewhere `grapher codex receive ./kit/`.
<!-- grapher:codex:end -->

