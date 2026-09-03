# grapher

Grapher is a local, general-purpose work graph for humans and autonomous agents. It preserves knowledge, lifecycle, truth, evidence, provenance, mission scope, and history in a searchable, inspectable form. Grapher knows; coordinating agents decide what work to perform, and auditors decide what evidence is sufficient.

Canonical files:

- .grapher/knowledge.json — durable graph truth and preserved history
- .grapher/vectors.json — derived semantic-search cache; safe to rebuild
- .grapher/config.json — project configuration and registry extensions
- .grapher/history.jsonl — append-only semantic mutation journal

## Install and initialize

Requires Python 3.10+.

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e ".[embed,dash]"
    grapher init --profile general --kind knowledge --all-stages
    grapher cursor install
    grapher codex install

Repeated and comma-separated kinds/stages are equivalent:

    grapher init --kind design --kind decision --stage designing,planning
    grapher init --kind design,decision --stage designing --stage planning

The default profile and domain are general. Profiles (general, software, product, research, campaign, operations) extend one schema; they do not fork it.

## General, non-software use

    grapher init --name museum-exhibit --profile product --kind brainstorm,design,roadmap --stage ideation,designing,planning
    grapher add --id goal-visitors --type goal --title "Visitor goal" --content "Visitors understand how prairie wetlands store carbon." --status canonical_spec --stage designing
    grapher add --id task-install --type task --title "Install central case" --content "Rig and level the central specimen case." --status current --workflow-state active --stage launching --owners facilities
    grapher link task-install goal-visitors --rel satisfies
    grapher checkpoint create --title "Exhibit readiness" --nodes goal-visitors,task-install
    grapher audit

Configured custom node types and relations in .grapher/config.json are accepted by authoring and validation.

## Graph kind and lifecycle stage

Kinds describe what relationships a graph emphasizes: knowledge, brainstorm, concept, requirements, decision, design, dependency, roadmap, implementation, launch, operations, or retrospective.

Stages describe where work sits: ideation → designing → planning → developing → launching → maintaining. Kinds and stages are independent and may both be plural. Aliases such as design, development, launch, and maintenance serialize canonically.

## Truth status

Truth status describes interpretation: unclassified, proposed, current, canonical_spec, superseded, historical, rejected, or deprecated. It is not a completion flag. Preserve replaced facts and link them in the canonical direction:

    grapher curate supersede NEW_NODE OLD_NODE
    grapher curate status NODE historical

Contradictions remain explicit with the contradicts relation; a newer timestamp alone does not resolve disagreement.

## Workflow state

Work state is independent of truth: not_started, active, blocked, completed, cancelled, on_hold, or not_applicable.

    grapher add --type task --title "Approve labels" --workflow-state blocked --status current --content "Awaiting accessibility review."

A completed task can produce a current finding; a field handoff does not imply acceptance or audit completion.

## Verification and evidence

Verification is unverified, partially_verified, verified, failed, or not_applicable. Verified claims should carry evidence or a verified_by/evidenced_by edge.

    grapher add --type claim --title "Case supports rated load" --verification verified --status current --evidence '{"type":"measurement","ref":"load-test-2026-09-03","summary":"Held 200 kg for 30 minutes"}'

Evidence supports tests, files, documents, images, measurements, observations, commits, conversations, external sources, commands, logs, and other domain evidence. Audit reports verified nodes without evidence.

## Relations

Precise built-ins cover references, dependencies, blockers, evidence, decisions, ownership, supersession, contradiction, mission records, handoffs, acceptances, and audits. related remains a legal low-information fallback. Validation diagnoses dangling, duplicate, self-superseding, and cyclic supersession edges.

    grapher link HANDOFF MISSION_GENERATION --rel applies_to
    grapher link ACCEPTANCE MISSION_GENERATION --rel accepts
    grapher link AUDIT MISSION_GENERATION --rel audits

## Search

Semantic search falls back to lexical search when embeddings are unavailable. Hybrid combines both. Truth-aware reranking considers status, verification, query intent, scope/generation, provenance integrity, and checkpoints; recency is not dominant.

    grapher search "what is true now" --project terminal --mission ubuntu-prototype --generation gen-2 --exclude-superseded --explain-ranking --json
    grapher search "original requirement" --status canonical_spec --mode lexical
    grapher search "why did the failure happen" --include-history
    grapher search "next roadmap" --workflow-state active --status proposed

Filters include kind, stage, status, workflow state, verification, type, tag, project, mission, generation, actor, role, and as-of time. History and superseded nodes remain searchable by default; --current-only and --exclude-superseded narrow current-state retrieval. Ranking explanations name semantic/base, status, verification, provenance, scope, intent, checkpoint, recency, and edge-context components.

## Checkpoints

A checkpoint is a traceable current-state snapshot linked to sources with derived_from edges.

    grapher checkpoint create --title "Current exhibit state" --nodes goal-visitors,task-install
    grapher checkpoint refresh CHECKPOINT_ID --dry-run
    grapher checkpoint refresh CHECKPOINT_ID --yes
    grapher checkpoint list

Refresh is review-first: preview reports changed sources and contradictions. Audit marks a checkpoint stale when supporting state changes, fails verification, is superseded/rejected, gains contested/invalidated provenance, or participates in a contradiction.

## Provenance

Nodes can record actor, role, session, source mechanism, integrity, and an opaque external attestation reference. Integrity is unknown, declared, verified, contested, or invalidated. Grapher records provenance; it does not authenticate actors or infer authority from names, titles, paths, or prose. Verified provenance requires external attestation.

    grapher add --type handoff --title "Field handoff" --actor codex-field --role field-agent --session session-abc --provenance-integrity declared
    grapher curate provenance RECORD invalidated --reason "role-boundary interference"
    grapher curate provenance RECORD verified --attestation agent-hub:event:123

## Project, mission, and generation scope

Scope is optional and keeps project, mission, and reopened generations distinct:

    grapher add --type mission --title "Prototype generation 2" --project terminal --mission ubuntu-prototype --generation gen-2 --status current --workflow-state active

CLI flags override environment defaults. External systems may set GRAPHER_WORKSPACE_ID, GRAPHER_PROJECT_ID, GRAPHER_MISSION_ID, GRAPHER_GENERATION_ID, GRAPHER_ACTOR_ID, GRAPHER_ACTOR_ROLE, GRAPHER_SESSION_ID, GRAPHER_SOURCE, and GRAPHER_ATTESTATION_REF. Values remain declared unless a trusted caller supplies attestation and explicitly requests verified integrity.

## Mutation history and finalized records

Canonical nodes remain fast to read, while every semantic save appends immutable structured transitions to `history.jsonl`. Each transition has a stable ID, affected entity, typed change, previous/resulting values, timestamp, actor/source kind, phase, and correlation ID. Optional rationale, evidence references, decision/requirement IDs, and supersession/override IDs preserve why state changed. Actor kinds are `human`, `agent`, `system_tool`, and `migration_import`; phases keep `proposed`, `executed`, `observed`, `verified`, and `canonical` distinct. Existing hash-only journal lines remain readable.

    grapher add --type decision --id verify-release --title "Request verification" --phase proposed --actor-kind human --actor owner --reason "Release gate"
    grapher add --type event --id verification-failed --title "Verification failed" --verification failed --phase observed --actor-kind system_tool --actor pytest --decision-id verify-release --history-evidence-ref "pytest tests/" --operation-id release-check-7
    grapher history --entity verification-failed --json
    grapher history --operation release-check-7 --json

Canonical writes use temporary file, fsync, and atomic replace. If journal append fails, Grapher rolls the canonical graph back. Reads never reconstruct current state from history.

    grapher add --type acceptance --id release-acceptance --title "Release accepted" --content "Accepted against checklist R7." --finalize
    grapher curate finalize release-acceptance

Ordinary semantic rewriting or merging of finalized records is rejected. Correct them with a new node and supersedes. --force-finalized exists only for explicit administrative recovery and is journaled.

## Audit and validation

Validation performs structural/schema checks without mutation. Audit additionally reports type/stage/status/workflow/verification/provenance distributions, low-information relations, isolated and weak nodes, pending ingest, contradictions, supersession health, verified-without-evidence, stale checkpoints, and cross-generation ambiguity.

    grapher validate --json
    grapher audit --json

## Migration

Version 1 graphs remain readable without migration. Migration is lossless, idempotent, validated before atomic replacement, backed up by default, and journaled. Inference is separate and explicit.

    grapher migrate --graph tests/fixtures/cassio-brain.json --to 2 --dry-run --infer
    grapher migrate --graph /path/to/cassio-brain.json --to 2 --yes
    grapher audit --graph /path/to/cassio-brain.json
    grapher migrate infer-preview --graph /path/to/knowledge.json
    grapher migrate infer-apply --graph /path/to/knowledge.json --only-high-confidence --yes

Use --no-backup only when an external backup exists. Migration does not rewrite prose or silently replace vague relations with guesses.

## Compaction

    grapher curate compact --topic "exhibit readiness" --dry-run

Compaction is a non-destructive review of repeated low-information relationships. Original nodes remain. Use checkpoints and explicit curation to consolidate current state without deleting disagreement or crossing mission-generation boundaries.

## Deep ingest

    grapher ingest ./assets
    grapher scan ./assets

Ingest queues document/image/video/audio stubs. Semantic completion requires an enriching agent to actually read, view, watch, or listen and replace every pending stub with dense grounded content. A path is only a locator. Pending zero plus a content-level search is the acceptance check; unsupported media inspection must be disclosed, never invented.

## Cursor and Codex integration

    grapher cursor install --force
    grapher codex install --force
    grapher codex export ./transplant --name "exhibit-design" --description "Current exhibit decisions"
    grapher codex receive ./transplant

Generated guidance requires search before work, deep-media understanding, graph-worthy updates during and after work, honest verification/evidence, supersession instead of history deletion, and mission/provenance preservation. Core services remain agent-agnostic.

## Dashboard

    grapher dash --view provenance
    grapher dash --host 127.0.0.1 --port 8050 --open

Dash reads the same normalized v1/v2 model as the CLI and never migrates on open. Selectable views are Knowledge, Lifecycle, Dependency, Decision, Roadmap, Current State, History/Supersession, Operations, and Provenance/Mission History. Shared filters cover type, truth, lifecycle, verification, mission generation, and text. Detail shows full content, evidence, scope, provenance, dates, finalization, and relations. Dashboard downloads provide interactive HTML, filtered JSON (explicitly non-canonical), node CSV, and edge CSV; Plotly provides PNG export. Reload refreshes the cached normalized graph and deterministic layout.

## Software profile example

    grapher init --profile software --domain software --kind knowledge,implementation,decision --stage designing,developing,maintaining
    grapher add --type requirement --title "Token lifetime" --status canonical_spec --content "Access tokens expire after 15 minutes."
    grapher add --type finding --title "Token TTL implemented" --status current --verification verified --evidence '{"type":"test","ref":"pytest tests/test_auth.py"}'

## Development

Default tests avoid the large embedding model:

    ./scripts/test.sh -v

Optional embedding integration uses a larger memory cap:

    ./scripts/test-embed.sh -v

Reusable application boundaries live in grapher.store, model, graph, search, audit, migrate, curate, and checkpoint. Future Agent Hub and Auditor integrations can call these directly without a network service.
