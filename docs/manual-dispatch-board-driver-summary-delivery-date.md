# Manual Dispatch Board: Driver Summary Delivery Date

## Summary

Driver Summary now has its own Delivery Date view control. This separates the operational Dispatch Date from the customer/order Delivery Date shown inside driver cards.

## Date Concepts

- Dispatch Date is the operational board date used for manual assignment records.
- Delivery Date is the customer/order delivery date.
- Driver Summary Delivery Date controls which assigned Orders are visible inside Driver Summary cards.
- Task Pool remains a global unassigned active Order pool and is not filtered by Driver Summary Delivery Date.
- Task Pool can apply its own optional Delivery Date display filter without changing assignment membership or Driver Summary state.

## Driver Summary Behavior

- Driver cards remain visible and stable when Driver Summary Delivery Date changes.
- Driver card order and membership do not change just because a delivery date is selected.
- Each driver card shows only assigned Orders where:
  - assignment `dispatch_date` equals the selected Dispatch Date.
  - order `delivery_date` equals the selected Driver Summary Delivery Date.
- If a driver has no assigned Orders for the selected Delivery Date, the card stays visible and shows an empty state.

## Vehicle Selection Scope

Vehicle selection is scoped by:

```text
driver_id + dispatch_date + delivery_date
```

Selecting or clearing a vehicle for one Delivery Date does not overwrite vehicle selections for another Delivery Date.

## Editable Order Delivery Date

- Active Orders can update `delivery_date` through Edit Order.
- An unassigned Order stays in Task Pool after its Delivery Date changes; it may disappear only from the current Task Pool display filter if the new date no longer matches.
- An assigned Order keeps its existing Dispatch Date / Driver / Trip assignment after its Delivery Date changes.
- Driver Summary then shows that assigned Order only when its updated Delivery Date matches the selected Driver Summary Delivery Date.
- Existing vehicle selections for other Delivery Dates are preserved.

Legacy vehicle selections that existed before this scope was added are migrated with:

```text
delivery_date = dispatch_date
```

## Final Trip Summary

Final Trip Summary generation, save, history, and export use both dates:

- `dispatch_date`
- `delivery_date`

Generated summaries include only assigned Orders for the selected Dispatch Date and selected Driver Summary Delivery Date.

Duplicate saved summary protection is scoped to:

```text
driver_id + dispatch_date + delivery_date
```

Excel export uses saved snapshot data and includes both Dispatch Date and Delivery Date.

## Excluded Work

This change does not add automatic assignment, route optimization, ETA, geocoding, Google Maps logic, CP-SAT, automatic driver selection, automatic vehicle selection, capacity blocking, or zone blocking.
