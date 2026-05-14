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
- `main` is the stable release branch and should be the normal base for new work.
- Never work directly on `main` unless explicitly instructed.
- Use short-lived feature, fix, chore, docs, or deployment branches.
- Run `git status` before committing.
- Commit only files related to the current task.
- Do not commit local runtime data, cache files, generated database files, or temporary scripts.

## Branch, Release, and NAS Deployment Policy

### Stable Branch

- `main` represents reviewed, tested, deployable code.
- `main` should be the normal base for new feature branches.
- Do not commit directly to `main` unless explicitly instructed.
- Changes should normally enter `main` through a pull request.

### Feature Branches

- New work should start from the latest `main`.
- Use branch names like:
  - `feature/<short-description>`
  - `fix/<short-description>`
  - `chore/<short-description>`
  - `docs/<short-description>`
  - `deployment/<short-description>` only for deployment-specific preparation.
- Avoid continuing ordinary feature work on old long-running branches.

### Existing Long-Running Branches

- `deployment/nas-internal-office-release` was used to prepare the NAS/internal office deployment.
- After `deployment/nas-internal-office-release` is merged to `main`, do not keep adding ordinary feature work to it.
- Future deployment fixes should normally start from `main` using a new `chore/` or `deployment/` branch.
- Treat `feature/manual-dispatch-board` as a historical/legacy development branch after `main` has absorbed the current stable work.
- Do not use `feature/manual-dispatch-board` as the default base for new work unless explicitly requested.

### Release Tags

- Stable office deployments should be tagged from `main`.
- Use tags like:
  - `release-office-v1`
  - `release-office-v1.1`
  - `release-office-v1.2`
- Always record the exact deployed commit.

### NAS Deployment Source

- After the NAS deployment PR is merged, the NAS should normally deploy from `main` or from a release tag.
- Before updating NAS production:
  - confirm no one is actively dispatching
  - run a WAL-safe SQLite backup
  - record the current deployed commit
  - pull the intended branch or tag
  - rebuild/restart Docker
  - validate `/health` and the core workflow
- Do not deploy random feature branches to NAS production unless explicitly approved.

### SQLite and Runtime Data Safety

- Never commit:
  - `data/*.sqlite`
  - `data/*.sqlite3`
  - `*.sqlite-wal`
  - `*.sqlite-shm`
  - `backups/`
  - `.env`
  - local runtime files
- SQLite must remain on NAS local storage.
- Do not directly share/open the SQLite file from client computers.
- Keep one app instance by default because SQLite is the database.
- Do not add multiple Docker replicas/workers for the SQLite deployment unless the database architecture changes.

### Pull Request Requirements

Every PR should include:

- Summary
- Files changed
- Business behavior impact
- Deployment impact
- Tests run
- Risks / rollback notes

### Business Logic Protection

- The Manual Dispatch Board remains a manual office workflow.
- Do not add auto-dispatch, route optimization, ETA, geocoding, Google Maps, CP-SAT, automatic driver selection, automatic vehicle selection, automatic trip planning, capacity blocking, or zone blocking unless explicitly requested.

## Future Feature Architecture Policy

Future features must preserve the modular Manual Dispatch Board architecture. Do not add new functionality by placing large blocks of unrelated logic into central files.

### General Rules

- New features must be placed in the correct domain module.
- Keep `frontend/app.js` as the browser entry point and orchestration layer.
- Do not put large render functions, API calls, or workflow implementations directly into `frontend/app.js`.
- Frontend API calls must stay centralized in `frontend/js/api/manual-dispatch-api.js`.
- Shared frontend state belongs in `frontend/js/state/app-state.js`.
- Read-only state lookup and derived state belong in `frontend/js/state/selectors.js`.
- Rendering code belongs in `frontend/js/render/`.
- Render modules should receive data and callbacks.
- Render modules must not call `fetch`.
- User workflow logic belongs in `frontend/js/actions/`.
- Action modules may coordinate validation, API calls, state updates, and rerender callbacks.
- Shared helper logic belongs in `frontend/js/utils/`.
- Backend route handlers should remain thin and delegate to services.
- `ManualDispatchService` should remain a stable facade, not a large implementation file again.
- New backend business behavior should normally live under `backend/services/manual_dispatch/`.
- Repository classes should handle persistence only, not business workflow rules.
- Excel export behavior should stay isolated in the existing Excel export services.
- Do not mix API access, state mutation, DOM rendering, validation, and persistence in the same function.
- Do not duplicate API endpoint strings, DOM selectors, validation logic, or formatting logic across files.
- Keep refactors and feature changes separate where possible.
- Do not add speculative abstractions that are not required by the current feature.
- Do not introduce `localStorage` or extra `sessionStorage` usage unless explicitly required and reviewed.
- Do not change API routes, database schema, persisted fields, response fields, DOM IDs, CSS class names, user-facing labels, Final Summary snapshot semantics, or Excel output unless the feature explicitly requires it.

### Prohibited Feature Creep

Do not add the following unless explicitly requested:

- auto-dispatch
- automatic driver selection
- automatic vehicle selection
- automatic order grouping
- automatic trip planning
- route optimization
- ETA prediction
- geocoding
- Google Maps integration
- CP-SAT or other optimization engines
- capacity blocking
- zone blocking
- hidden browser-storage persistence

Manual Dispatch Board must remain a manual dispatch workflow unless the product requirement explicitly changes.

### New Feature Placement Checklist

Before implementing a new feature, answer:

1. Which backend domain does this feature belong to?
2. Which frontend layer does this feature affect?
   - API
   - state/selectors
   - render
   - actions
   - utils
3. Does this require a database schema change?
4. Does this require an API contract change?
5. Does this affect Excel export behavior?
6. Does this affect Final Trip Summary snapshot semantics?
7. Does this affect existing DOM IDs, CSS classes, or user-facing labels?
8. What tests protect the old behavior?
9. What tests protect the new behavior?
10. Does this require browser smoke testing?

### Test Requirements For New Features

At minimum, run:

```powershell
python -m compileall backend tests
python -m unittest discover -s tests -v
node --check frontend/app.js
Get-ChildItem frontend -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
git diff --check
```

When frontend behavior changes, also run the Playwright browser smoke test.

When API behavior changes, add or update route-level tests.

When Excel behavior changes, verify the workbook with `openpyxl`.

When Final Trip Summary behavior changes, verify:

- generated snapshot behavior
- saved snapshot behavior
- finalized order visibility
- history loading
- export uses saved snapshot data, not live mutable data

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
