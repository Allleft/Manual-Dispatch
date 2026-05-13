# Phase 16: Product Details, Load-Unit Exclusivity, and Final Summary Export

## Summary

Phase 16 adds structured Product Details to Manual Dispatch Board Orders and enforces a single load unit per Order:

- Pallets only, or
- Bags only.

It also carries Product Details into saved Final Trip Summary snapshots and the Final Summary Excel workbook.

No routing, ETA, geocoding, optimization, automatic assignment, automatic vehicle selection, or automatic driver selection was added.

## Product Detail Data Model

Orders may now include zero or more product lines.

Each product line stores:

- `product_name`
- `quantity`
- `unit`

Allowed units:

- `PALLETS`
- `BAGS`

SQLite persistence uses:

- `order_product_lines`

Saved Final Trip Summary row snapshots also store serialized product-line details so historical summaries do not change when live Order data is edited later.

Legacy Orders without product lines remain valid. Their Product Detail display reads:

```text
No product details recorded.
```

## Load-Unit Exclusivity

An Order must use exactly one load-unit family when quantities are present:

- Palletized Orders have `pallet_quantity > 0` and `loose_bags_quantity = 0`.
- Bag Orders have `loose_bags_quantity > 0` and `pallet_quantity = 0`.

The backend rejects:

- mixed pallet and bag totals on the same Order,
- mixed product-line units inside one Order,
- product-line units that do not match the Order load unit,
- non-positive product-line quantities.

The frontend mirrors the rule:

- entering Pallets clears/disables Bags,
- entering Bags clears/disables Pallets,
- save attempts surface a clear validation error if invalid state is present.

## Add/Edit Order Behavior

Add Order and Edit Order now include a Product Details editor:

- Add Product Line
- Product Name
- Quantity
- Unit
- Remove

Product details may be left empty when the existing order rules otherwise allow the Order to save.

Existing order lifecycle behavior remains unchanged:

- active Orders can still be edited,
- cancelled/finalized visibility rules remain governed by the existing workflow,
- assigned Orders preserve their assignment when edited.

## Product Detail UI

Order detail popups now include:

```text
Product Detail
```

When opened, product lines render in a numbered, readable form:

```text
1. colour singlet 10kg    3 Pallets
2. pure white singlet 10kg    2 Pallets
```

or:

```text
1. colour singlet 10kg    5 Bags
```

The same detail popup is used from Task Pool and Driver Summary entry points.

## Final Trip Summary Snapshot Behavior

Final Trip Summary remains scoped by:

- Dispatch Date
- Driver Summary Delivery Date

Phase 16 adds Product Details to each saved snapshot row while preserving the existing historical rule:

- saved summaries do not auto-update after live Order edits,
- product lines are copied into the saved snapshot,
- legacy Orders without product lines show `No product details recorded.`.

The summary table now presents:

- Product Details
- Load

instead of relying on a blank single Product cell plus a pallet-only number.

## Excel Export

Saved Final Trip Summary Excel export now includes:

- Dispatch Date
- Delivery Date
- Saved By
- Product Details
- Load

Multiple product lines are written into one Product Details cell separated by line breaks, for example:

```text
1. colour singlet 10kg - 3 Pallets
2. pure white singlet 10kg - 2 Pallets
```

Exports continue to use saved Final Trip Summary snapshot records, not live mutable Order data.

The workbook does not include:

- passwords,
- password hashes,
- password salts,
- admin reset codes,
- Generated At,
- Saved At.

## Validation Coverage

Automated tests cover:

- pallet product lines,
- bag product lines,
- mixed-unit rejection,
- invalid product quantity rejection,
- Add/Edit persistence,
- Final Summary snapshot preservation,
- Excel Product Details output,
- static frontend presence of Product Detail controls,
- existing manual dispatch workflows remaining green.

