# Separate Delivery and OP SHOP Workspaces Specification

**Approved:** 2026-06-23
**Implementation branch:** `feature/separate-delivery-and-opshop-workspaces`
**Original base:** `805e08dfd86da67a2f703afce61dfe8810649db8`

## Objective

Manual Dispatch provides two independent operational workspaces. Delivery Orders use Delivery Run Sheets; OP SHOP pickups use Pickup Collections. Each module owns its scoped board, generated/saved snapshots, locks, history, and export while preserving manual office assignment and legacy Final Summary compatibility.

## Current Information Architecture

```text
Home
  Order Delivery
    Task Pool
    Trip Summary
    Delivery Run Sheets
    Saved Run Sheet History
  OP SHOP Pickup
    Task Pool
      Regular
      Oncall
      Countryside
      Manage Templates
    Trip Summary
    Pickup Collections
    Saved Pickup Collection History
```

### Canonical OP SHOP Routes

| Route | Responsibility |
| --- | --- |
| `#opshop/task-pool/regular` | Regular live tasks and assignment drafts |
| `#opshop/task-pool/oncall` | Request-created Oncall tasks and assignment drafts |
| `#opshop/task-pool/countryside` | Countryside tasks and route-group assignment |
| `#opshop/templates` | Regular/Oncall templates plus Countryside groups/memberships |
| `#opshop/trip-summary` | Pickup Date review grouped by driver/category |
| `#opshop/collections` | Generated and Saved Pickup Collections, lifecycle, and export |
| `#opshop/history` | Saved Pickup Collections by actual Pickup Date, full immutable Weight Sheet preview, and per-record export |

Legacy aliases normalize without duplicate history entries:

- `#opshop`, `#opshop/task-pool`, and `#opshop/regular` -> Regular
- `#opshop/oncall` -> Oncall
- `#opshop/countryside` -> Countryside
- malformed `#opshop/task-pool/*` -> Regular

The hash route is the subtype source of truth. Subtype navigation does not reload the scoped board and therefore preserves pending assignment drafts and explicit `Unassigned` values.

## Workspace Boundaries

| Rule | Delivery | OP SHOP |
| --- | --- | --- |
| Task type | `ORDER` | `OPSHOP_PICKUP` |
| Snapshot | Delivery Run Sheet | Pickup Collection |
| Generated lock | Captured Delivery tasks and vehicle target | Captured/target OP SHOP tasks |
| Saved lock | Delivery assignment + vehicle for driver/date | OP SHOP assignment for driver/date |
| Totals | Pallets and loose bags | No Delivery totals |
| Export | Delivery-only workbook | OP SHOP-only workbook |

Saving one module must not lock or mutate the other. The same driver/date may have both a Saved Delivery Run Sheet and a Saved OP SHOP Pickup Collection.

## OP SHOP Task Pool Semantics

### Regular

- Active schedules ensure visible tasks idempotently.
- Add/view/edit/soft-delete reuse the established pickup task lifecycle.
- A source-backed template default driver is materialized once as an actual assignment when an eligible task is created or through the controlled source-driver backfill.
- Persisted source assignments immediately appear in Current Assignee, Assigned To, and Trip Summary without a pending draft or Apply click.
- Later user changes remain drafts until Apply. Once persisted, a manual reassignment or explicit `Unassigned` wins and is not overwritten by board loads, refresh, navigation, or rendering.

### Oncall

- Templates never create actual tasks automatically.
- Staff use Add Pickup Task, then may view/edit/soft-delete the live task.
- A template-derived task receives its source-backed default assignment once at creation; an ad hoc/no-default task remains Unassigned.
- Assignment changes remain drafts until Apply.

### Countryside

- Countryside remains `OPSHOP_PICKUP + ON_CALL + pickup_category=COUNTRYSIDE`.
- Task Pool route-group assignment creates/restores live tasks for active memberships.
- Live task detail/edit/delete is distinct from route definition and membership management.
- `#opshop/templates` contains route create/rename/soft-disable, membership add/move/remove, and route-template detail.

Generated/Saved reserved tasks do not appear as editable Task Pool records. Past `assigned_to_locked` tasks retain disabled mutation controls. Backend lock enforcement remains authoritative.

## Pickup Collection Lifecycle

1. OP SHOP Trip Summary filters assigned pickups by Pickup Date and groups Regular, Oncall, and Countryside separately under each driver.
2. Generate persists a `GENERATED` immutable snapshot and reserves captured pickup tasks.
3. Cancel Generated removes only that generated snapshot and restores editable tasks.
4. Save transitions the generated snapshot to `SAVED`.
5. Saved collections remain immutable history and are exported from snapshot rows, not live tasks.

Read-only detail and export routes are not migration-write guards. Scoped mutations and lifecycle writes return migration guidance until legacy saved records are represented by validated independent snapshots.

## Saved History Workspaces

- `#delivery/history` queries Delivery Run Sheets by `delivery_date + status=SAVED`; it never adds `dispatch_date`.
- `#opshop/history` queries Pickup Collections by `pickup_date + status=SAVED`; it never adds `dispatch_date`.
- Each result may therefore contain distinct saved records from multiple Dispatch Dates. Dispatch Date is displayed as record metadata, not used as a History filter.
- Delivery History reuses the full DAILY RUN SHEET paper snapshot; OP SHOP History reuses the full Pickup Collection Weight Sheet snapshot.
- History owns independent in-memory dates/results, guards stale date responses, and exposes per-record Excel export only. Generate, Save, Cancel, assignment, unassignment, and editing remain operational-page actions.

## Legacy Compatibility and Migration

- Legacy Final Summary tables, routes, saved history, and workbook behavior remain available.
- `tools/migrate_legacy_final_summaries_to_workspaces.py` is dry-run by default.
- Apply requires `--apply --yes`, creates and integrity-checks a timestamped SQLite backup, and writes all records transactionally.
- Readiness requires exactly one matching `SAVED` independent header and the matching number of child rows for each legacy module section.
- Any legacy `GENERATED` Final Summary blocks both scoped workspaces.
- Legacy records are not deleted or rewritten.

See [the migration runbook](separate-delivery-and-opshop-workspaces-migration.md).

## Out of Scope

- Deleting or changing legacy Final Summary contracts.
- Optimizer, CP-SAT, route optimization, ETA, maps, geocoding, automatic dispatch, automatic driver/vehicle selection, automatic trip planning, or capacity/zone blocking.
- Destructive SQLite migration or committing runtime databases.

## Acceptance Criteria

- Delivery snapshots contain only Orders and Delivery totals.
- OP SHOP snapshots contain only pickups and no Delivery totals/trips.
- Regular, Oncall, and Countryside operational CRUD is reachable in canonical scoped routes.
- Regular/Oncall template and Countryside route management is reachable at `#opshop/templates`.
- Browser refresh, copied links, Back, and Forward preserve canonical subtype behavior.
- Persisted source defaults require no Apply; later manual drafts survive subtype navigation and Apply remains their persistence boundary.
- Generated and Saved lifecycle state survives refresh/restart.
- Delivery and OP SHOP Saved History are independent routes queried by actual service date across Dispatch Dates, display full immutable papers, and expose export-only actions.
- Delivery remains unchanged by OP SHOP navigation, management, drafts, and collections.
- New and existing SQLite databases initialize safely and repeatedly.

## Validation

Automated coverage lives in the `test_workspace_*` modules and existing OP SHOP regression suite. Browser and copied-database validation follows [the OP SHOP workspace smoke checklist](opshop-workspace-smoke-test-checklist.md).

## Rollback

Changes are committed as focused stages on the feature branch and can be reverted independently. Snapshot schema additions are additive; rollback must not delete legacy or independent history data.
