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
- After discoveries: `grapher add` / `grapher link` with dense, embeddable summaries.
- To transplant: `grapher codex export ./kit/` then elsewhere `grapher codex receive ./kit/`.
<!-- grapher:codex:end -->
