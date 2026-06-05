# OP SHOP / Final Trip Summary Smoke Test Checklist

Use this checklist to manually validate OP SHOP pickup locking and Final Trip Summary behavior with the local full-test SQLite database.

## Scope

This smoke test verifies:

- Regular OP SHOP pickup assignment and locking.
- Oncall OP SHOP pickup creation, assignment, and locking.
- Countryside route group pickup creation, assignment, and locking.
- Generate lock before Save and Export.
- Saved Final Summary hard lock after Save and Export.
- Reopening OP SHOP lists does not clear saved OP SHOP assignments.
- Browser refresh or app restart preserves saved locks.
- OP SHOP remains separate from Delivery Order Trip 1 / Trip 2 rows and delivery totals.
- Delivery Order workflow still works.

This checklist does not test optimizer, CP-SAT, route optimization, ETA, maps, geocoding, or automatic dispatch.

## Start App With Test Database

Run from the repository root:

```powershell
$env:MANUAL_DISPATCH_DB_PATH = "C:\Users\Albert Fang\Desktop\Delivery V2\data\manual_dispatch_full_test.sqlite3"
$env:MANUAL_DISPATCH_SEED_DEMO_DATA = "0"
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\start_office_trial.ps1 -Port 8130
```

Open:

```text
http://127.0.0.1:8130
```

Record:

- Dispatch Date:
- Driver Summary Delivery Date:
- Driver:
- Vehicle:
- Regular pickup task id:
- Oncall pickup task id:
- Countryside pickup task id:
- Saved Final Summary id:

## Pre-Test Safety

- Confirm no production DB is selected.
- Confirm the app is using `data\manual_dispatch_full_test.sqlite3`.
- Do not use the real office dispatch database for this smoke test.
- If this DB should be reset, take a local copy first.

## Test A: Regular OP SHOP Pickup

1. Open the board.
2. Set Dispatch Date to the test date.
3. Open `Regular OP SHOP Pickup List`.
4. Pick one visible future/current Regular pickup.
5. Confirm it is not locked.
6. Select an Assigned to driver.
7. Click `Close`.
8. Confirm the pickup appears in the driver's `OP SHOP PICKUPS` section in Driver Summary.
9. Confirm it does not appear under Trip 1 or Trip 2 Delivery Order rows.
10. Confirm delivery totals do not change because of the OP SHOP pickup.

Expected:

- `opshop_pickup_tasks.status = ASSIGNED`.
- `opshop_pickup_tasks.driver_id` is the selected driver.
- `opshop_pickup_tasks.trip_no = trip1`.
- `manual_dispatch_assignments` has an `OPSHOP_PICKUP` row.

## Test B: Oncall OP SHOP Pickup

1. Open `Oncall OP SHOP Pickup List`.
2. Click `Add Pickup Task`.
3. Select an Oncall template.
4. Select Pickup Date.
5. Select Assigned to driver.
6. Save the pickup task.
7. Confirm the pickup appears in the Oncall list.
8. Click `Close`.
9. Confirm it appears in the driver's `OP SHOP PICKUPS` section for the pickup date.
10. Confirm it does not appear under Trip 1 or Trip 2 Delivery Order rows.

Expected:

- Oncall pickup is an actual `OPSHOP_PICKUP` task.
- `run_type = ON_CALL`.
- Assignment uses `trip1`.
- Delivery totals remain unchanged by OP SHOP.

## Test C: Countryside Route Group Pickup

1. Open `Countryside OP SHOP Pickup List`.
2. Click `Assign Route Group`.
3. Select a Route Group with active route templates.
4. Select Pickup Date.
5. Select Assigned Driver.
6. Click `Assign Route Group`.
7. Confirm pickup tasks are created for route templates in that route group.
8. Confirm created Countryside pickups appear in the list.
9. Confirm assigned Countryside pickups appear in Driver Summary under `OP SHOP PICKUPS`.
10. Confirm they do not appear under Trip 1 or Trip 2 Delivery Order rows.

Expected:

- Countryside is still `task_type = OPSHOP_PICKUP`.
- Countryside schedules use `run_type = ON_CALL`.
- Countryside schedules/items use `pickup_category = COUNTRYSIDE`.
- Assignment uses `trip1`.

## Test D: Generate Lock Before Save

1. Assign at least one OP SHOP pickup to a driver for the selected Driver Summary Delivery Date.
2. Optionally assign one Delivery Order to the same driver/date for a mixed summary.
3. Click `Generate` on that driver card.
4. Confirm the generated Final Trip Summary preview appears.
5. Confirm OP SHOP pickups appear only in the Final Summary `OP SHOP PICKUPS` section.
6. Confirm OP SHOP pickups do not appear in Delivery Trip 1 / Trip 2 rows.
7. Confirm pallet and loose bag totals only count Delivery Orders.
8. Confirm the Driver Summary editable card no longer shows those generated tasks.
9. Confirm the vehicle dropdown is disabled after Generate.
10. Reopen the relevant OP SHOP list before Save and Export.
11. Confirm generated OP SHOP pickups show:

```text
Locked - Generated in Final Trip Summary
```

12. Confirm Assigned to dropdown is disabled.
13. Confirm Edit/Delete are unavailable.

Expected:

- Generate locks the current page state.
- OP SHOP live DB assignment is not cleared by Generate.
- Saved lock is not yet persistent until Save and Export.

## Test E: Save Final Summary Lock After Save

1. In the generated Final Summary preview, click `Save and Export`.
2. Confirm Excel export completes.
3. Confirm saved Final Summary appears in History.
4. Reopen the relevant OP SHOP list.
5. Confirm the same OP SHOP pickups still show the assigned driver.
6. Confirm Assigned to dropdown is disabled.
7. Confirm the lock message is:

```text
Locked - Final Trip Summary saved
```

8. Close the OP SHOP list.
9. Reopen it again.
10. Confirm the saved assignment was not cleared.

Expected:

- Saved lock persists.
- OP SHOP live assignment remains traceable.
- Closing OP SHOP lists does not clear saved locked assignments.

## Test F: Refresh / Restart Persistence

1. Refresh the browser.
2. Reopen the board for the same Dispatch Date and Driver Summary Delivery Date.
3. Confirm the driver/date shows saved Final Summary lock.
4. Reopen Regular / Oncall / Countryside OP SHOP lists.
5. Confirm saved pickups still show assigned driver and saved lock message.
6. Stop the app.
7. Restart using the same startup command above.
8. Repeat steps 2-5.

Expected:

- Saved lock survives browser refresh.
- Saved lock survives app restart.
- OP SHOP task and assignment rows remain assigned.

## Test G: Final Summary History Verification

1. Open Final Summary History.
2. Select the saved summary date.
3. Open the saved summary for the tested driver.
4. Confirm Delivery rows appear in Trip 1 / Trip 2 only when Delivery Orders were included.
5. Confirm OP SHOP pickups appear in a separate `OP SHOP PICKUPS` section.
6. Confirm OP SHOP snapshot data matches the pickup at Generate/Save time.
7. Confirm live OP SHOP list changes do not mutate saved history snapshot.

Expected:

- History uses saved snapshot data.
- OP SHOP snapshot rows are separate from Delivery rows.

## Test H: Delivery Order Workflow Regression

1. Add or pick a Delivery Order for the test Driver Summary Delivery Date.
2. Assign it to a driver and Trip 1 or Trip 2.
3. Choose a vehicle.
4. Generate Final Trip Summary.
5. Confirm Delivery Order appears in the correct Trip section.
6. Confirm totals count Delivery Order pallets / loose bags.
7. Save and Export.
8. Confirm saved driver/date is hard locked.
9. Try assigning another Delivery Order to the saved driver/date.
10. Confirm assignment is blocked.
11. Try changing vehicle for the saved driver/date.
12. Confirm vehicle change is blocked.

Expected:

- Delivery workflow still works.
- Saved Final Summary hard lock blocks further Delivery assignment and vehicle changes.
- OP SHOP behavior does not change Delivery totals.

## SQLite DB Verification Queries

Use the same database path:

```powershell
$db = "C:\Users\Albert Fang\Desktop\Delivery V2\data\manual_dispatch_full_test.sqlite3"
```

If `sqlite3` is available:

```powershell
sqlite3 $db "SELECT pickup_task_id, schedule_id, pickup_date, status, driver_id, trip_no, generated_from, updated_at FROM opshop_pickup_tasks WHERE pickup_task_id = '<PICKUP_TASK_ID>';"
```

### Pickup Task Status

```sql
SELECT
  pickup_task_id,
  schedule_id,
  pickup_date,
  status,
  driver_id,
  trip_no,
  generated_from,
  updated_at
FROM opshop_pickup_tasks
WHERE pickup_task_id = '<PICKUP_TASK_ID>';
```

Expected after Save and Export:

- `status = ASSIGNED`
- `driver_id = <DRIVER_ID>`
- `trip_no = trip1`

### Assignment Row

```sql
SELECT
  assignment_id,
  dispatch_date,
  task_type,
  task_id,
  driver_id,
  trip_no,
  assigned_at,
  updated_at
FROM manual_dispatch_assignments
WHERE task_type = 'OPSHOP_PICKUP'
  AND task_id = '<PICKUP_TASK_ID>';
```

Expected after Save and Export:

- One row remains.
- `task_type = OPSHOP_PICKUP`
- `driver_id = <DRIVER_ID>`
- `trip_no = trip1`

### Saved Final Summary Row

```sql
SELECT
  summary_id,
  dispatch_date,
  delivery_date,
  driver_id,
  driver_name_snapshot,
  vehicle_rego_snapshot,
  total_pallets,
  total_loose_bags,
  generated_at,
  saved_at,
  saved_by_account_name
FROM final_trip_summaries
WHERE dispatch_date = '<DISPATCH_DATE>'
  AND delivery_date = '<DELIVERY_DATE>'
  AND driver_id = '<DRIVER_ID>'
ORDER BY saved_at DESC;
```

Expected:

- A saved summary row exists.
- `total_pallets` and `total_loose_bags` count Delivery Orders only.

### Saved OP SHOP Snapshot Row

```sql
SELECT
  row_id,
  summary_id,
  row_no,
  pickup_task_id_snapshot,
  opshop_name_snapshot,
  suburb_snapshot,
  street_address_snapshot,
  pickup_date_snapshot,
  run_type_snapshot,
  pickup_frequency_snapshot,
  status_snapshot
FROM final_trip_summary_opshop_pickup_rows
WHERE pickup_task_id_snapshot = '<PICKUP_TASK_ID>'
ORDER BY row_no;
```

Expected:

- A snapshot row exists for the OP SHOP pickup.
- `pickup_date_snapshot = <DELIVERY_DATE>`.
- OP SHOP appears in this table, not in Delivery row totals.

### Confirm OP SHOP Is Not In Delivery Rows

```sql
SELECT
  row_id,
  summary_id,
  task_type,
  order_id_snapshot,
  company_name_snapshot,
  suburb_snapshot
FROM final_trip_summary_rows
WHERE summary_id = '<SUMMARY_ID>'
  AND task_type <> 'ORDER';
```

Expected:

- No rows returned.

## Pass / Fail Notes

Record any failures with:

- Dispatch Date:
- Driver Summary Delivery Date:
- Driver:
- Pickup task id:
- Summary id:
- Browser action taken:
- Expected result:
- Actual result:
- Console error, if any:
- Relevant SQL query output:
