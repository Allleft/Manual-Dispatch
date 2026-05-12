# AGENTS.md

## 1. Project Governance Rules
- Preserve existing business behavior unless explicitly requested.
- Prefer the smallest safe change.
- Do not perform unrelated refactors or cleanup.
- Keep changes consistent with the existing project style and architecture.
- If scope is unclear, stop and clarify before changing behavior.

## 2. Existing Dispatch Contract
- Existing top-level output keys must remain unchanged:
  - `plans`
  - `order_assignments`
  - `exceptions`
- Do not rename or remove these keys.
- Do not change existing `dispatch_optimizer` logic unless explicitly requested.
- Do not change the existing assignment algorithm, CP-SAT logic, routing logic, zone scoring logic, or current output contract unless explicitly requested.

## 3. Manual Dispatch Board Scope
- The Manual Dispatch Board is a separate manual workflow.
- It is not an auto-dispatch algorithm.
- The layout must be top-bottom:
  - Top: Task Pool
  - Bottom: Driver Summary
- Do not use a left-right layout unless explicitly requested.
- Keep this workflow separate from existing automated dispatch behavior.

## 4. Manual Dispatch Board MVP Rules
- Task Pool shows unassigned Orders.
- Each Order card shows only Suburb and Pallet quantity.
- If the Order only has Loose Bags, Pallet quantity should display as 0.
- Each Order card can select Driver.
- Each Order card can select `trip1` or `trip2`.
- Default trip is `trip1`.
- Assign button moves the Order into the selected Driver card.
- Driver Summary shows one card per Driver.
- Each Driver card groups assigned Orders by `trip1` and `trip2`.
- Each Driver card has a Choose Vehicle dropdown.
- Vehicle dropdown options show vehicle rego.
- Vehicle assignment is at Driver + Dispatch Date level.
- Future task types such as Pickup should be supported through `task_type` and `task_id`.

## 5. Forbidden in Manual Dispatch Board MVP
The Manual Dispatch Board MVP must not include:
- auto-assignment algorithm
- CP-SAT
- route optimization
- ETA calculation
- geocoding
- Google Maps integration
- automatic driver selection
- automatic vehicle selection
- automatic trip planning
- capacity-based blocking
- zone-based blocking
- automatic order grouping
- automatic route sequencing

## 6. Data Model Direction
Planned entities:
- Order
- Driver
- Vehicle
- Manual Dispatch Assignment
- Manual Driver Vehicle Assignment

Recommended assignment structure:
- `task_type`
- `task_id`
- `driver_id`
- `trip_no`
- `dispatch_date`

Future task types may include:
- `ORDER`
- `PICKUP`
- `RETURN`
- `SPECIAL_TASK`

## 7. Vehicle Assignment Rule
- Vehicle selection belongs to Driver + Dispatch Date.
- Vehicle is not assigned to each individual Order in the MVP.
- Example: John + 2026-05-05 -> ABC123.
- John's `trip1` and `trip2` should use the same selected vehicle by default.

## 8. Git Workflow
- Never work directly on `main` unless explicitly instructed.
- Use feature branches.
- Recommended branch name for this project: `feature/manual-dispatch-board`.
- Run `git status` before committing.
- Commit only files related to the current task.
- Do not commit local runtime data, cache files, generated database files, or temporary scripts.

## Active Refactor Branch Policy

For the current comprehensive Manual Dispatch Board structure refactor, all code changes must be committed and pushed to:

`refactor/manual-dispatch-structure`

Do not push refactor commits to `main` or `feature/manual-dispatch-board`.

`feature/manual-dispatch-board` is the source baseline branch for this refactor. It should remain available as the stable pre-refactor comparison branch.

Before making any code change, confirm the current branch with:

```bash
git branch --show-current
```

If the current branch is not `refactor/manual-dispatch-structure`, stop and switch to the correct branch before editing files.

Every completed refactor phase must be committed and pushed to:

```bash
git push origin refactor/manual-dispatch-structure
```

Final reports must include:

- current branch
- commit hash
- pushed status
- files changed
- tests run
- any behavior-preservation risks

## 9. GitHub Push Rules
- After completing a task, commit and push to the current feature branch.
- After every completed phase, commit and push the current feature branch to `https://github.com/Allleft/Manual-Dispatch.git` unless the user explicitly says not to push.
- Use `origin` for `https://github.com/Allleft/Manual-Dispatch.git`; if `origin` is missing, add it before pushing.
- Use clear commit messages.
- Example commit messages:
  - `docs: add manual dispatch board governance`
  - `feat: add manual dispatch board layout skeleton`
  - `feat: implement manual order assignment`
  - `test: add manual dispatch board service tests`
  - `fix: preserve task pool after unassign`
- Final report must include branch, commit hash, pushed status, files changed, and test results.

## 10. Testing Requirements
Recommended checks:
- `python -m unittest discover -s tests -v`
- `node --check frontend/app.js`
- `node --check frontend/overrides.js`

Rules:
- Run relevant tests before and after functional changes.
- If a file does not exist, report it clearly.
- Do not claim a test passed if it was not run.
- If tests fail, report the failing command, error summary, likely cause, files involved, and whether it appears pre-existing.

## 11. Validation Report Format
Every completed task must end with:

```markdown
## Summary
- ...

## Files Changed
- ...

## Tests Run
- Command:
- Result:

## Git
- Branch:
- Commit:
- Pushed to GitHub:

## Notes / Risks
- ...
```

## 12. Safe Change Policy
- Prefer small staged changes.
- Do not delete files unless explicitly requested.
- Do not rename public functions, API routes, database tables, or output fields unless explicitly requested.
- Do not modify unrelated files.
- If a larger refactor is needed, propose the plan first.

## 13. Documentation Rules
- New feature documentation should go under `docs/`.
- Manual Dispatch Board documents may include:
  - `docs/manual-dispatch-board-phase0.md`
  - `docs/manual-dispatch-board-mvp.md`
  - `docs/manual-dispatch-board-api.md`
  - `docs/manual-dispatch-board-db.md`
- Documentation should distinguish current implemented behavior, planned future behavior, and not included in this phase.

## 14. Manual Dispatch Board Phase Control
- Phase 0: governance, documentation, baseline checks only. No UI, backend, or database implementation.
- Phase 1: data model planning and schema design.
- Phase 2: page skeleton.
- Phase 3: frontend manual assignment flow.
- Phase 4: vehicle selection logic.
- Phase 5: backend API.
- Phase 6: database persistence.
- Phase 7: business hints.
- Phase 8: review/export.
- Phase 9: future Pickup/task extension.
- Do not jump phases unless explicitly instructed.

## 15. Final Reminder
The Manual Dispatch Board is a manual office workflow. The goal is to make it easy for staff to manually assign Orders to Driver + Trip + Vehicle. Do not turn this MVP into an optimization engine.
