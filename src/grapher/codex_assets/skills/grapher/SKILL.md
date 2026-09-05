---
name: grapher
description: >-
  Use grapher knowledge graphs and Codex transplant kits. Trigger when the user
  mentions grapher, GRAPHER_CONTEXT, grapherpack, transplanting an idea, or
  loading exported agent context. Read .grapher/GRAPHER_CONTEXT.md fully before
  acting when present.
---

# Grapher for Codex

You are working with a project that may contain a **grapher** knowledge graph and an optional full-fidelity context dump for transplanted ideas.

## When a transplant kit or context is present

1. If `.grapher/GRAPHER_CONTEXT.md` exists, **read the entire file** before coding or exploring. Do not skim — node `content` holds the idea (including deep image/video/audio understanding).
2. Then use retrieval:
   ```bash
   grapher search "<question>"
   grapher get <id>
   grapher neighbors <id>
   ```
3. If the user points at a kit directory or `.grapherpack.json` and it is not received yet:
   ```bash
   grapher codex receive <DIR|PACK>
   ```
   Then read the written `.grapher/GRAPHER_CONTEXT.md`.

## Typed semantic entries

For durable reasoning/work records, use canonical semantic types:

`observation`, `problem`, `question`, `hypothesis`, `requirement`, `constraint`, `proposal`, `decision`, `task`, `implementation`, `test`, `result`, `failure`, `lesson`.

Their `--content` must satisfy the exact JSON contract documented in `docs/SEMANTIC_ENTRY_SCHEMA.md`. Missing fields, wrong field types, unexpected fields, and filler such as `TBD` or `investigate later` are rejected. Empty semantic stubs are temporary only; current, canonical, verified, or finalized semantic records must be complete. Integrations can inspect contracts with `grapher.semantic.semantic_contract()` and `semantic_contracts()`.

## Git transport

Keep the active conversation small and use Grapher as durable context. After `git pull`, run `grapher sync` before relying on local graph state. Before pushing graph-worthy changes, run `grapher validate`, `grapher audit`, and `grapher publish`, then commit `.grapher/shared/`. Never commit `.grapher/knowledge.json`, vectors, local history, or sync state.

## Exporting an idea for another project

```bash
grapher codex export ./transplant/ --name "<idea>" --description "<one line>"
```

That writes pack JSON + `GRAPHER_CONTEXT.md` + a short README.

## Non-negotiables

- Paths are locators; **understanding** is in `content`.
- Do not treat empty or filename-only media nodes as successful knowledge.
- Keep working context compact; retrieve only relevant graph slices and persist durable detail outside the conversation.
- Prefer grapher over rediscovering after context is loaded.
- Preserve uncertainty: hypotheses are hypotheses; results require evidence; decisions require rationale.
