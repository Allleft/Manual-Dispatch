# Separate Delivery and OP SHOP Workspaces Specification

**Task:** Separate Delivery and OP SHOP workspaces
**Approved:** 2026-06-23
**Base:** `origin/main` at `805e08dfd86da67a2f703afce61dfe8810649db8`

## Objective

Replace the shared Manual Dispatch Board experience with two independent operational
workspaces. Delivery Orders use Delivery Run Sheets; OP SHOP pickups use Pickup
Collections. Each module owns its generated/saved snapshots, locks, history, and
exports while retaining the existing manual assignment workflow and legacy Final
Summary compatibility.

## In Scope

- Additive, idempotent SQLite tables for Delivery Run Sheets and OP SHOP Pickup
  Collections.
- Independent repository, service, lock, API, history, and Excel export paths.
- Scoped Delivery and OP SHOP board payloads.
- Workspace Home and separate Delivery/OP SHOP hash routes.
- Dry-run-first migration of saved legacy Final Summaries into independent snapshots.
- Tests, README, and migration documentation for the new workflow.

## Out of Scope

- Deleting or changing legacy Final Summary tables or API contracts.
- Changing existing order, OP SHOP template, pickup creation, or assignment semantics
  except where required to split module-specific generated/saved locks.
- Optimizer, CP-SAT, routing, ETA, maps, geocoding, automatic dispatch, automatic
  driver/vehicle selection, or capacity/zone blocking.
- Destructive SQLite migrations or runtime database commits.

## Atomic Subtasks

1. Add independent snapshot schema, dataclasses, and repository persistence.
2. Add module-specific services, locks, scoped board APIs, and exporters.
3. Add the controlled legacy migration tool and migration tests.
4. Add Workspace Home, module routes, state, actions, and renderers.
5. Update documentation and complete full automated/browser validation.

## Acceptance Criteria

- Delivery snapshots contain only `ORDER` rows and Delivery totals.
- OP SHOP snapshots contain only `OPSHOP_PICKUP` rows and no Delivery totals/trips.
- Saving one module does not lock or mutate the other module.
- The same driver/date can have both a saved Delivery Run Sheet and saved OP SHOP
  Pickup Collection.
- Existing legacy Final Summary tables, APIs, and saved history remain readable.
- Existing Regular, Oncall, Countryside, Attaché import, driver, and vehicle workflows
  remain available.
- New and existing SQLite databases initialize safely and repeatedly.

## Rollback

All work is isolated on `feature/separate-delivery-and-opshop-workspaces`. Each atomic
subtask is committed separately and can be reverted independently. The additive pilot
does not remove or rewrite legacy data.
