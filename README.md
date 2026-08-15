# Stock Dependency Tracker

A tool that takes large-cap "anchor" stocks (NVDA, AAPL, TSM, …) and discovers
smaller "satellite" stocks whose returns are statistically correlated with each
anchor, producing a weighted, explorable dependency graph.

Live: FastAPI on Render, React frontend on Vercel, Postgres for prices +
company metadata. Full history in [docs/progress_impl_docs/what-has-been-built.md](docs/progress_impl_docs/what-has-been-built.md).

For conventions and tech stack, see [CLAUDE.md](CLAUDE.md).
For the original design and full roadmap, see
[stock_correlation_graph_roadmap.md](stock_correlation_graph_roadmap.md).

## Docs

### Where the project is going
- [progress_impl_docs/what-has-been-built.md](docs/progress_impl_docs/what-has-been-built.md) — how we got to a deployed, CI-gated system.
- [progress_impl_docs/next-steps.md](docs/progress_impl_docs/next-steps.md) — the menu of what's next, with a decision framework.
- [progress_impl_docs/track-a-product-plan.md](docs/progress_impl_docs/track-a-product-plan.md) — the full "make it a real product" track (precomputed correlations → scheduled jobs → portfolio analysis → regime surfacing).
- [progress_impl_docs/track-a-worktree-plan.md](docs/progress_impl_docs/track-a-worktree-plan.md) — how to parallelise Track A across worktrees.
- [progress_impl_docs/research-track.md](docs/progress_impl_docs/research-track.md) — the portfolio research workspace that extends Track A.

### Production topology & roadmap
- [prod_roadmap/current-architecture.md](docs/prod_roadmap/current-architecture.md) — the deployed system today.
- [prod_roadmap/target-architecture.md](docs/prod_roadmap/target-architecture.md) — the end-state design.
- [prod_roadmap/production-roadmap.md](docs/prod_roadmap/production-roadmap.md) — the plan that got the app deployed: hygiene, Docker, Postgres, CI/CD, hosting.

### Backend deep-dives
- [backend_docs/correlation-mechanism.md](docs/backend_docs/correlation-mechanism.md) — the correlation math: what data points, how prices become returns, pair alignment, stability score, Phase 4 methodology, worked example.
- [backend_docs/universe-roadmap.md](docs/backend_docs/universe-roadmap.md) — Phase 7 (post-frontend): replacing the hardcoded 55-ticker satellite universe with a dynamically-screened one — sourcing, curation-vs-scale tradeoff, statistical/compute risks at scale.

### Frontend
- [frontend_docs/frontend-roadmap.md](docs/frontend_docs/frontend-roadmap.md) — the Phase 5 frontend broken into a step-by-step build sequence.
- [frontend_docs/frontend-build-plan.md](docs/frontend_docs/frontend-build-plan.md) — the frontend-roadmap.md Step 0 questions answered: locked design tokens, rough `frontend/` structure, local dev workflow.
- [frontend/README.md](frontend/README.md) — how to run the frontend locally.

See also [.claude/skills/network-graph-style/SKILL.md](.claude/skills/network-graph-style/SKILL.md)
for the concrete color/sizing rules used by every graph renderer.
