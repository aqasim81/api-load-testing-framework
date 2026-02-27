# LoadForge Implementation Checklist

> This checklist tracks the implementation of each phase through a disciplined
> workflow cycle. Complete each step in order before moving to the next phase.
>
> **Reference documents:**
> - [Product Requirements](./prd.md)
> - [Full Implementation Plan](./implementation_plan.md) — architecture, interfaces, dependencies
> - [Project Overview](./project.md)

---

## Phase 0: Code Quality Infrastructure

- [x] Planning
- [x] Implementation
- [x] Validation (`make validate` passes)

---

## Phase 1: Foundation + Scenario DSL

> [Detailed plan](./phases/phase-1-foundation-scenario-dsl.md) |
> Dependencies: None

- [x] **Plan** — Review [phase plan](./phases/phase-1-foundation-scenario-dsl.md) and the relevant sections of [implementation_plan.md](./implementation_plan.md)
- [x] **Review plan** — Confirm scope, file list, and acceptance criteria are clear; adjust if needed
- [x] **Implement** — Build all files listed in the phase plan
- [x] **Review implementation** — Code review: types, docstrings, error handling, conventions per CLAUDE.md
- [x] **Test** — Run `make validate` (format, lint, typecheck, unit tests)
- [x] **Fix issues** — Address any failures from validation or review
- [x] **Update checklist** — Mark completed items above; update CLAUDE.md "Current Status"
- [x] **Ready for next phase** — All criteria met, proceed to Phase 2

---

## Phase 2: Traffic Patterns

> [Detailed plan](./phases/phase-2-traffic-patterns.md) |
> Dependencies: None (can overlap with Phase 1)

- [x] **Plan** — Review [phase plan](./phases/phase-2-traffic-patterns.md) and the relevant sections of [implementation_plan.md](./implementation_plan.md)
- [x] **Review plan** — Confirm scope, file list, and acceptance criteria are clear; adjust if needed
- [x] **Implement** — Build all files listed in the phase plan
- [x] **Review implementation** — Code review: types, docstrings, error handling, conventions per CLAUDE.md
- [x] **Test** — Run `make validate` (format, lint, typecheck, unit tests)
- [x] **Fix issues** — Address any failures from validation or review
- [x] **Update checklist** — Mark completed items above; update CLAUDE.md "Current Status"
- [x] **Ready for next phase** — All criteria met, proceed to Phase 3

---

## Phase 3: Single-Worker Engine

> [Detailed plan](./phases/phase-3-single-worker-engine.md) |
> Dependencies: Phase 1, Phase 2

- [x] **Plan** — Review [phase plan](./phases/phase-3-single-worker-engine.md) and the relevant sections of [implementation_plan.md](./implementation_plan.md)
- [x] **Review plan** — Confirm scope, file list, and acceptance criteria are clear; adjust if needed
- [x] **Implement** — Build all files listed in the phase plan
- [x] **Review implementation** — Code review: types, docstrings, error handling, conventions per CLAUDE.md
- [x] **Test** — Run `make validate` + `uv run pytest tests/integration/ -v`
- [x] **Fix issues** — Address any failures from validation or review
- [x] **Update checklist** — Mark completed items above; update CLAUDE.md "Current Status"
- [ ] **Ready for next phase** — All criteria met, proceed to Phase 4

---

## Phase 4: Multi-Worker Distribution

> [Detailed plan](./phases/phase-4-multi-worker-distribution.md) |
> Dependencies: Phase 3 | **HARDEST PHASE**

- [ ] **Plan** — Review [phase plan](./phases/phase-4-multi-worker-distribution.md) and the relevant sections of [implementation_plan.md](./implementation_plan.md)
- [ ] **Review plan** — Confirm scope, file list, and acceptance criteria; pay special attention to shared memory design and fallback strategy
- [ ] **Implement** — Build all files listed in the phase plan (start with Queue-based approach for correctness)
- [ ] **Review implementation** — Code review: types, docstrings, error handling, multiprocessing safety, race conditions
- [ ] **Test** — Run `make validate` + `uv run pytest tests/integration/ -v`
- [ ] **Fix issues** — Address any failures from validation or review
- [ ] **Update checklist** — Mark completed items above; update CLAUDE.md "Current Status"
- [ ] **Ready for next phase** — All criteria met, proceed to Phase 5

---

## Phase 5: CLI Interface

> [Detailed plan](./phases/phase-5-cli-interface.md) |
> Dependencies: Phase 4

- [ ] **Plan** — Review [phase plan](./phases/phase-5-cli-interface.md) and the relevant sections of [implementation_plan.md](./implementation_plan.md)
- [ ] **Review plan** — Confirm scope, file list, and acceptance criteria are clear; adjust if needed
- [ ] **Implement** — Build all files listed in the phase plan
- [ ] **Review implementation** — Code review: types, docstrings, error handling, conventions per CLAUDE.md
- [ ] **Test** — Run `make validate` + `uv run pytest tests/e2e/ -v`
- [ ] **Fix issues** — Address any failures from validation or review
- [ ] **Update checklist** — Mark completed items above; update CLAUDE.md "Current Status"
- [ ] **Ready for next phase** — All criteria met, proceed to Phase 6

---

## Phase 6: Post-Run Reports

> [Detailed plan](./phases/phase-6-post-run-reports.md) |
> Dependencies: Phase 4 (MetricStore)

- [ ] **Plan** — Review [phase plan](./phases/phase-6-post-run-reports.md) and the relevant sections of [implementation_plan.md](./implementation_plan.md)
- [ ] **Review plan** — Confirm scope, file list, and acceptance criteria are clear; adjust if needed
- [ ] **Implement** — Build all files listed in the phase plan
- [ ] **Review implementation** — Code review: types, docstrings, error handling, template correctness
- [ ] **Test** — Run `make validate`
- [ ] **Fix issues** — Address any failures from validation or review
- [ ] **Update checklist** — Mark completed items above; update CLAUDE.md "Current Status"
- [ ] **Ready for next phase** — All criteria met, proceed to Phase 7

---

## Phase 7: Live React Dashboard

> [Detailed plan](./phases/phase-7-live-react-dashboard.md) |
> Dependencies: Phase 4 (Aggregator), Phase 5 (CLI)

- [ ] **Plan** — Review [phase plan](./phases/phase-7-live-react-dashboard.md) and the relevant sections of [implementation_plan.md](./implementation_plan.md)
- [ ] **Review plan** — Confirm scope, file list, and acceptance criteria are clear; adjust if needed
- [ ] **Implement (Python)** — Build FastAPI server and broadcaster
- [ ] **Implement (React)** — Build all dashboard components
- [ ] **Build dashboard** — Run `cd dashboard && npm run build` to output static assets
- [ ] **Review implementation** — Code review: Python types/docstrings, TypeScript strict, WebSocket correctness
- [ ] **Test** — Run `make validate` + `uv run pytest tests/integration/test_dashboard.py -v`
- [ ] **Fix issues** — Address any failures from validation or review
- [ ] **Update checklist** — Mark completed items above; update CLAUDE.md "Current Status"
- [ ] **Ready for next phase** — All criteria met, proceed to Phase 8

---

## Phase 8: Polish, Documentation, Examples

> [Detailed plan](./phases/phase-8-polish-documentation-examples.md) |
> Dependencies: All phases

- [ ] **Plan** — Review [phase plan](./phases/phase-8-polish-documentation-examples.md) and the relevant sections of [implementation_plan.md](./implementation_plan.md)
- [ ] **Review plan** — Confirm the scope of polish, docs, and CI/CD tasks
- [ ] **Implement** — Complete all documentation, examples, CI/CD, and polish tasks
- [ ] **Review implementation** — Full project review: README accuracy, example scenarios work, CI passes
- [ ] **Test** — Run `make validate` + `uv run pytest -v` (all tests) + manual verification plan from implementation_plan.md
- [ ] **Fix issues** — Address any remaining issues
- [ ] **Update checklist** — Mark all items complete; finalize CLAUDE.md "Current Status"
- [ ] **Project complete** — All 8 phases done, ready for GitHub showcase
