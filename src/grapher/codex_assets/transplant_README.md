# Grapher Codex transplant kit

This directory is a portable idea transplant for **Codex**.

## Contents

- `idea.grapherpack.json` — machine pack (nodes, edges, optional vectors)
- `GRAPHER_CONTEXT.md` — **full-fidelity** markdown of every node’s content + relationships (read this first)

## Receive into a project

```bash
cd /path/to/target-project
grapher codex receive /path/to/this/kit
```

That will:

1. Unpack the graph into `.grapher/knowledge.json`
2. Write `.grapher/GRAPHER_CONTEXT.md`
3. Install/update the grapher section in `AGENTS.md` and the Codex skill

Then start Codex in the target project. It should read `.grapher/GRAPHER_CONTEXT.md` fully before acting.
