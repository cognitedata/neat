Identifies views with query performance issues that cannot be resolved with requires.

## What it does
Detects views where no valid requires constraint solution exists:

1. **CDF-only containers**: Views mapping only to CDF built-in containers.
   Since CDF containers cannot be modified, no requires can be added.

2. **No valid solution**: The optimal MST structure doesn't create a connected
   hierarchy for this view (e.g., convergent edges pointing to a shared hub).

## Why is this important?
These views will have suboptimal query performance that CANNOT be fixed by
adding or removing requires constraints. The only solutions require restructuring:
- Add a view-specific container that requires the others
- Restructure the view to use different containers

## Example
View `Test` maps to containers `Valve`, `InstrumentEquipment`, and `Tag`.
The optimal constraints are `Valve → Tag` and `InstrumentEquipment → Tag`,
but this creates a convergent structure where neither Valve nor InstrumentEquipment
can reach each other. The view needs a new container or restructuring.