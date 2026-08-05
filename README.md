# Docs

High-level summaries of what's been built, phase by phase. For the original design and full roadmap, see [stock_correlation_graph_roadmap.md](stock_correlation_graph_roadmap.md). For a quick-reference on conventions and tech stack, see [CLAUDE.md](CLAUDE.md).

- [phase1.md](docs/phase1.md) — single-anchor proof of concept: fetch → correlate → rank → static graph.
- [phase2.md](docs/phase2.md) — multi-anchor pipeline, rolling-correlation stability scoring, market-cap/volume node metadata, combined graph with cross-anchor queries.
- [phase3.md](docs/phase3.md) — interactive HTML graph (pyvis/vis.js): sector color-coding, market-cap sizing, hover tooltips, light/dark support, and a companion summary table.
- [phase4.md](docs/phase4.md) — advanced analytics: Spearman rank correlation as the primary ranking metric, partial (market-adjusted) and sector-relative correlation, time-lagged cross-correlation, regime-break detection, and an anchor-relatedness ("correlation of correlations") matrix.
- [phase4-5.md](docs/phase4-5.md) — modular REST API refactor: repositories (Postgres-ready seam) → services → FastAPI routes, replacing the four `run_phaseN.py` scripts with one CLI built on the same services the API uses.
- [correlation-mechanism.md](docs/correlation-mechanism.md) — deep dive on the correlation math itself: exactly what data points are used (today, and what a V2 engine could add), how prices become returns, how pairs are aligned, how the stability score is derived, the full Phase 4 methodology, and a worked numeric example.
- [production-roadmap.md](docs/production-roadmap.md) — the plan from here to a deployed product: engineering hygiene (lint/format/type-check), Docker, Postgres migration, CI/CD (GitHub Actions), the Phase 5 frontend (stack, functional spec, and a ready-to-use build prompt), and deployment/hosting.
- [frontend-roadmap.md](docs/frontend-roadmap.md) — the Phase 5 frontend broken into a step-by-step build sequence: for each step, the questions to answer yourself first and the follow-up prompt that results, covering performance, responsiveness, flexibility, and visual style end to end.
- [frontend-build-plan.md](docs/frontend-build-plan.md) — frontend-roadmap.md's Step 0 questions, answered and reconciled: locked design tokens, a rough `frontend/` file structure, and the local dev/iteration workflow for actually building it.
- [universe-roadmap.md](docs/universe-roadmap.md) — Phase 7 (post-frontend): replacing the hardcoded 55-ticker satellite universe with a dynamically-screened, filterable one — sourcing, the curation-vs-scale tradeoff, the CompanyRepository seam it plugs into, and the new statistical/compute risks at scale.

See also [.claude/skills/network-graph-style/SKILL.md](.claude/skills/network-graph-style/SKILL.md) for the concrete color/sizing rules used by every graph renderer.
