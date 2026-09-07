# M12 — Documentation and Full-Suite Completion

M12 closes the numbered Grapher modernization sequence. It does not introduce another architecture layer. It reconciles the human/agent documentation with the behavior proven in M1–M11 and makes the complete governance and regression suite the closure authority.

## Completion architecture

```mermaid
flowchart LR
    SHIPPED["Shipped Grapher behavior\nsrc/grapher/*\ninception: ffe7023\ncurrent: M12 branch"]
    DOCS["Human + agent documentation\nREADME.md + docs/*\ninception: ffe7023\ncurrent: M12 branch"]
    ACCEPT["Named acceptance suite\ntests/test_m11_acceptance_suite.py\ninception: ffe7023\ncurrent: M12 branch"]
    REGRESSION["Full regression suite\ntests/*\ninception: ffe7023\ncurrent: M12 branch"]
    GOVERN["Governance gates\nscripts/check_docs_index.py + self-state/truth gates\ninception: ffe7023\ncurrent: M12 branch"]
    CLOSE["Modernization sequence complete\ndocs/ROADMAP.md\ninception: ffe7023\ncurrent: M12 branch"]

    SHIPPED --> DOCS
    SHIPPED --> ACCEPT
    SHIPPED --> REGRESSION
    DOCS --> GOVERN
    ACCEPT --> CLOSE
    REGRESSION --> CLOSE
    GOVERN --> CLOSE
```

## Completion procedure

```mermaid
flowchart LR
    AUDIT["Audit docs against current CLI/contracts\nREADME.md + docs/*\ninception: ffe7023\ncurrent: M12 branch"]
    FIX["Correct stale or missing documentation\ndocs/*\ninception: ffe7023\ncurrent: M12 branch"]
    INDEX["Verify every human-facing doc is indexed\ndocs/INDEX.md\ninception: ffe7023\ncurrent: M12 branch"]
    SELF["Record M12 in Grapher self-state\n.grapher/shared/*\ninception: ffe7023\ncurrent: M12 branch"]
    TEST["Run governance + complete Python matrix\n.github/workflows/ci.yml\ninception: ffe7023\ncurrent: M12 branch"]
    COMPLETE["Only then mark M12 completed\ndocs/ROADMAP.md\ninception: ffe7023\ncurrent: M12 branch"]

    AUDIT --> FIX --> INDEX --> SELF --> TEST --> COMPLETE
```

## Closure criteria

M12 may be marked completed only when documentation describes the shipped M1–M11 interfaces without known contradictions, the documentation index gate passes, Grapher's versioned self-state records the M12 pass, the named M11 acceptance suite remains green, and the full supported Python test matrix plus truth/governance gates pass.

The five grandfathered `unclassified` records remain separately tracked maintenance debt unless explicitly curated during M12; they do not redefine the numbered modernization sequence.
