<!-- grapher:codex:start -->
## grapher

This project uses **grapher** for durable agent knowledge. `.grapher/knowledge.json` is local runtime state; Git-shared knowledge lives under `.grapher/shared/`.

**On session start / when using a transplanted idea:** if `.grapher/GRAPHER_CONTEXT.md` exists, **read that entire file first** before exploring or re-deriving. It is the full-fidelity transplant of the idea (every node’s deep content + relationships).

After pulling repository changes, hydrate shared knowledge before work:

```bash
grapher sync
grapher search "<question>"
grapher get <id>
grapher neighbors <id> --depth 2
```

Rules:

- Keep working context compact: retrieve only relevant slices, summarize instead of pasting large files/transcripts, avoid repeating known context, and store durable detail in Grapher or repo files rather than the conversation window.
- Prefer grapher search/get over rediscovering known context.
- Deep understanding of documents, images, video, and audio lives in node `content` — **paths alone are not knowledge**.
- For semantic types (`observation`, `problem`, `question`, `hypothesis`, `requirement`, `constraint`, `proposal`, `decision`, `task`, `implementation`, `test`, `result`, `failure`, `lesson`), write `--content` as the exact JSON contract documented in `docs/SEMANTIC_ENTRY_SCHEMA.md`; wrong types, filler, missing fields, and unexpected fields are rejected.
- Temporary empty semantic stubs are allowed while unclassified/unverified, but current, canonical, verified, or finalized semantic records must be complete.
- After discoveries: `grapher add` / `grapher link` with dense, grounded content and precise relations.
- Before pushing durable knowledge: run `grapher validate`, `grapher audit`, and `grapher publish`; commit `.grapher/shared/`, not local runtime graph/vector/history files.
- After pulling another agent's shared publication: run `grapher sync` before relying on local graph state.
- To transplant: `grapher codex export ./kit/` then elsewhere `grapher codex receive ./kit/`.
<!-- grapher:codex:end -->
