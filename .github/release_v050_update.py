from pathlib import Path


def replace(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected text not found in {path}: {old[:80]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


readme = Path("README.md")
text = readme.read_text(encoding="utf-8")

old_files = """Canonical files:

- .grapher/knowledge.json — durable graph truth and preserved history
- .grapher/vectors.json — derived semantic-search cache; safe to rebuild
- .grapher/config.json — project configuration and registry extensions
- .grapher/history.jsonl — append-only semantic mutation journal
"""
new_files = """Runtime files (local, not Git-shared):

- `.grapher/knowledge.json` — local canonical working graph
- `.grapher/vectors.json` — derived semantic-search cache; safe to rebuild
- `.grapher/config.json` — project configuration and registry extensions
- `.grapher/history.jsonl` — append-only local semantic mutation journal
- `.grapher/sync-state.json` — last synchronized shared graph hash

Git-shared knowledge:

- `.grapher/shared/knowledge.json` — deterministic normalized snapshot
- `.grapher/shared/manifest.json` — schema, graph hash, publication id, and embedding metadata
- `.grapher/shared/history/<publication-id>.json` — immutable publication record

Local graph/history/vector state should not be committed. `grapher publish` is the boundary that creates Git-safe shared state.
"""
if old_files not in text:
    raise SystemExit("README canonical-files block drifted")
text = text.replace(old_files, new_files)

transport_anchor = """The default profile and domain are general. Profiles (general, software, product, research, campaign, operations) extend one schema; they do not fork it.

"""
transport_section = """The default profile and domain are general. Profiles (general, software, product, research, campaign, operations) extend one schema; they do not fork it.

## Git transport

Normal work happens against the local graph. Share durable knowledge through Git with an explicit publish/sync boundary:

    grapher validate
    grapher audit
    grapher publish
    git add .grapher/shared
    git commit -m "grapher: publish project knowledge"
    git push

After pulling another agent's publication:

    git pull
    grapher sync

`grapher publish` refuses invalid graphs and writes a deterministic shared snapshot, manifest, and immutable publication record. `grapher sync` verifies the shared hash and refuses to overwrite unpublished local changes unless `--force` is explicit. Vectors remain local and are rebuilt from shared knowledge. See `docs/GIT_TRANSPORT.md`.

"""
if transport_anchor not in text:
    raise SystemExit("README transport insertion anchor drifted")
text = text.replace(transport_anchor, transport_section, 1)

old = 'grapher add --id task-install --type task --title "Install central case" --content "Rig and level the central specimen case." --status current --workflow-state active --stage launching --owners facilities'
new = 'grapher add --id task-install --type task --title "Install central case" --content \'{"action":"Rig and level the central specimen case","expected_outcome":"Central case is installed level and ready for exhibit use"}\' --status current --workflow-state active --stage launching --owners facilities'
if old not in text:
    raise SystemExit("README task-install example drifted")
text = text.replace(old, new)

old = 'grapher add --type task --title "Approve labels" --workflow-state blocked --status current --content "Awaiting accessibility review."'
new = 'grapher add --type task --title "Approve labels" --workflow-state blocked --status current --content \'{"action":"Approve final exhibit labels","expected_outcome":"Accessibility-reviewed labels are approved for production"}\''
if old not in text:
    raise SystemExit("README workflow example drifted")
text = text.replace(old, new)

typed_section = """## Typed semantic entries

Durable reasoning/work records use strict semantic contracts for `observation`, `problem`, `question`, `hypothesis`, `requirement`, `constraint`, `proposal`, `decision`, `task`, `implementation`, `test`, `result`, `failure`, and `lesson`.

For these types, `--content` must be a JSON object with the exact required fields for that type. Required values must have the documented type and substantive content; filler and unexpected fields are rejected. For example:

    grapher add --type decision --title "Use typed records" --status current \\
      --content '{"decision":"Normalize semantic entries at write time","rationale":"Downstream tools need stable machine-readable meaning"}'

    grapher add --type task --title "Verify transport" --status current --workflow-state active \\
      --content '{"action":"Run cross-checkout publish/sync verification","expected_outcome":"A second checkout hydrates the identical validated graph"}'

Temporary empty semantic stubs are allowed only while unclassified and unverified. Current, canonical, verified, or finalized semantic records must be complete. Programmatic integrations can inspect contracts with `grapher.semantic.semantic_contract()` and `semantic_contracts()`. See `docs/SEMANTIC_ENTRY_SCHEMA.md`.

## Relations
"""
if "## Relations\n" not in text:
    raise SystemExit("README relations anchor missing")
text = text.replace("## Relations\n", typed_section, 1)

old = 'grapher add --type requirement --title "Token lifetime" --status canonical_spec --content "Access tokens expire after 15 minutes."'
new = 'grapher add --type requirement --title "Token lifetime" --status canonical_spec --content \'{"requirement":"Access tokens expire after 15 minutes","acceptance_condition":"Authentication tests confirm 15-minute access-token expiry"}\''
if old not in text:
    raise SystemExit("README software requirement example drifted")
text = text.replace(old, new)

old = "Generated guidance requires search before work, deep-media understanding, graph-worthy updates during and after work, honest verification/evidence, supersession instead of history deletion, and mission/provenance preservation. Core services remain agent-agnostic."
new = "Generated guidance requires compact working context, search before work, deep-media understanding, strict typed semantic contracts, graph-worthy updates during and after work, honest verification/evidence, supersession instead of history deletion, mission/provenance preservation, and explicit publish/sync at the Git boundary. Core services remain agent-agnostic."
if old not in text:
    raise SystemExit("README integration summary drifted")
text = text.replace(old, new)
readme.write_text(text, encoding="utf-8")

agents = """<!-- grapher:codex:start -->
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
"""
Path("AGENTS.md").write_text(agents + "\n", encoding="utf-8")
Path("src/grapher/codex_assets/AGENTS.section.md").write_text(agents, encoding="utf-8")

codex_skill = Path("src/grapher/codex_assets/skills/grapher/SKILL.md")
ctext = codex_skill.read_text(encoding="utf-8")
old = "Their `--content` must be a JSON object containing the type-specific fields documented in `docs/SEMANTIC_ENTRY_SCHEMA.md`. Do not write free-form filler such as `TBD`, `investigate later`, or unsupported conclusions. Empty semantic stubs are temporary only; current, canonical, verified, or finalized semantic records must be complete."
new = "Their `--content` must satisfy the exact JSON contract documented in `docs/SEMANTIC_ENTRY_SCHEMA.md`. Missing fields, wrong field types, unexpected fields, and filler such as `TBD` or `investigate later` are rejected. Empty semantic stubs are temporary only; current, canonical, verified, or finalized semantic records must be complete. Integrations can inspect contracts with `grapher.semantic.semantic_contract()` and `semantic_contracts()`."
if old not in ctext:
    raise SystemExit("Codex skill semantic paragraph drifted")
ctext = ctext.replace(old, new)
anchor = "## Exporting an idea for another project"
if anchor not in ctext:
    raise SystemExit("Codex skill export anchor missing")
ctext = ctext.replace(anchor, """## Git transport

Keep the active conversation small and use Grapher as durable context. After `git pull`, run `grapher sync` before relying on local graph state. Before pushing graph-worthy changes, run `grapher validate`, `grapher audit`, and `grapher publish`, then commit `.grapher/shared/`. Never commit `.grapher/knowledge.json`, vectors, local history, or sync state.

## Exporting an idea for another project""", 1)
old = "- Prefer grapher over rediscovering after context is loaded."
new = "- Keep working context compact; retrieve only relevant graph slices and persist durable detail outside the conversation.\n- Prefer grapher over rediscovering after context is loaded."
if old not in ctext:
    raise SystemExit("Codex skill non-negotiable anchor missing")
ctext = ctext.replace(old, new)
codex_skill.write_text(ctext, encoding="utf-8")

cursor_rule = Path("src/grapher/cursor_assets/rules/grapher.mdc")
rtext = cursor_rule.read_text(encoding="utf-8")
anchor = "# grapher — shared agent knowledge\n\n"
if anchor not in rtext:
    raise SystemExit("Cursor rule title anchor missing")
rtext = rtext.replace(anchor, anchor + "**Keep working context compact.** Retrieve only relevant graph slices, summarize instead of pasting large files/transcripts, avoid repeating known context, and persist durable detail in Grapher or repo files rather than the active conversation.\n\n", 1)
anchor = "When multiple nodes cover the same topic, prefer **current** or **canonical_spec** status. Check supersession edges (`supersedes`) before treating older nodes as truth.\n\n"
if anchor not in rtext:
    raise SystemExit("Cursor rule truth anchor missing")
rtext = rtext.replace(anchor, anchor + """## Git transport

`.grapher/knowledge.json`, vectors, local history, and sync state are local runtime files. Git-shared knowledge lives under `.grapher/shared/`. After pulling repository changes, run `grapher sync`. Before pushing durable graph changes, run `grapher validate`, `grapher audit`, and `grapher publish`, then commit `.grapher/shared/`. Never overwrite unpublished local changes with `grapher sync --force` unless discarding them is intentional.

""", 1)
old = "For these types, `--content` is a JSON object with required type-specific fields (see `docs/SEMANTIC_ENTRY_SCHEMA.md`). Examples:"
new = "For these types, `--content` must satisfy the exact JSON contract (see `docs/SEMANTIC_ENTRY_SCHEMA.md`). Missing fields, wrong field types, unexpected fields, and filler are rejected. Programmatic integrations can inspect contracts with `grapher.semantic.semantic_contract()` and `semantic_contracts()`. Examples:"
if old not in rtext:
    raise SystemExit("Cursor rule semantic paragraph drifted")
rtext = rtext.replace(old, new)
cursor_rule.write_text(rtext, encoding="utf-8")

ingest_skill = Path("src/grapher/cursor_assets/skills/grapher-ingest/SKILL.md")
itext = ingest_skill.read_text(encoding="utf-8")
old = """6. Verify:
   ```bash
   grapher scan <DIR>
   grapher search "<a detail that only exists inside an image/video/audio you ingested>"
   ```"""
new = """6. Verify and publish durable shared knowledge:
   ```bash
   grapher scan <DIR>
   grapher search "<a detail that only exists inside an image/video/audio you ingested>"
   grapher validate
   grapher audit
   grapher publish
   ```
   Commit `.grapher/shared/`; keep local graph/vector/history/sync files out of Git."""
if old not in itext:
    raise SystemExit("Cursor ingest verification block drifted")
itext = itext.replace(old, new)
old = "- Do keep `content` dense and embeddable (not whole file dumps)"
new = "- Do keep working context compact and `content` dense/embeddable (not whole file dumps)"
if old not in itext:
    raise SystemExit("Cursor ingest density rule drifted")
itext = itext.replace(old, new)
ingest_skill.write_text(itext, encoding="utf-8")

Path(".cursor/rules").mkdir(parents=True, exist_ok=True)
Path(".cursor/skills/grapher-ingest").mkdir(parents=True, exist_ok=True)
Path(".cursor/rules/grapher.mdc").write_text(cursor_rule.read_text(encoding="utf-8"), encoding="utf-8")
Path(".cursor/skills/grapher-ingest/SKILL.md").write_text(ingest_skill.read_text(encoding="utf-8"), encoding="utf-8")

changelog = """# Changelog

## 0.5.0 — 2026-09-05

- Added strict typed semantic contracts for durable reasoning/work records, including exact allowed fields, field-type validation, filler rejection, and machine-readable contract introspection.
- Added Git-backed `grapher publish` / `grapher sync` transport with deterministic snapshots, graph hashes, manifests, immutable publication records, unpublished-change protection, and local vector rebuilds.
- Added compact-context guidance as a canonical agent workflow rule and synchronized generated Codex/Cursor documentation with the new schema and transport behavior.
- Updated human documentation and examples so semantic node commands satisfy the enforced contracts.
- Verified cross-checkout synchronization and recorded the 2026-09-05 maintenance baseline in Grapher's own shared graph.

## 0.4.1 — 2026-09-03

- Hardened finalized-record immutability, audited administrative deletion, mutation actor attribution, and provenance/history behavior.
"""
Path("CHANGELOG.md").write_text(changelog, encoding="utf-8")

replace("pyproject.toml", 'version = "0.4.1"', 'version = "0.5.0"')
replace("src/grapher/__init__.py", '__version__ = "0.4.1"', '__version__ = "0.5.0"')
