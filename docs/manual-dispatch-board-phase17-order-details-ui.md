# Phase 17: Order Details UI Alignment

## Summary

Phase 17 aligns the read-only Order Details modal with the Edit Order modal layout.

- Order Details now uses the same two-column form-style field grid as Edit Order.
- Order Details remains read-only.
- Edit Order remains fully editable.
- Product Detail display and Product Details editing behavior are preserved.

No dispatch rules, routing, optimization, Final Trip Summary snapshot behavior, or Excel export behavior changed.

## Order Details Layout

The read-only modal now follows the same field order as Edit Order:

1. Invoice #
2. Company Name
3. Phone
4. Delivery Address
5. Suburb
6. Postcode
7. Delivery Date
8. Zone
9. Urgency
10. Preferred Driver
11. Pallet Quantity
12. Loose Bags Quantity
13. Start Time
14. End Time
15. Note

The fields render inside the shared form-grid structure so Order Details and Edit Order stay visually aligned.

## Read-Only Behavior

Order Details uses disabled/read-only controls:

- Inputs and textareas are not editable.
- Selects are disabled.
- The user must still click `Edit` before changing Order data.

The read-only controls keep the same visual spacing and layout as Edit Order while avoiding accidental direct edits.

## Edit Order Behavior

Edit Order keeps the existing editable behavior:

- Delivery Date remains editable.
- Pallet/Bags exclusivity remains unchanged.
- Product Details remain editable.
- Save and Cancel Edit controls continue to work as before.

## Product Details

The Order Details header still exposes:

- `Product Detail`
- `Edit`
- `Cancel Order`
- `Close`

The Product Detail view continues to display numbered product lines, or:

```text
No product details recorded.
```

when an Order has no product lines.

## Validation

Phase 17 is protected by:

- frontend static contract checks for shared read-only/edit field structure,
- existing Order/Add/Edit/Product Details coverage,
- browser validation of read-only Order Details, editable Edit Order, Product Detail display, and persisted edits.
