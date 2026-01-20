Identifies views with query performance issues that cannot be resolved.
This is likely to be caused by unintended modeling choices.

## What it does
Detects views where no valid requires constraint solution exists:

1. **View maps only to CDF built-in containers**:
   Since CDF containers cannot be modified, no requires can be added.

2. **No valid solution**:
   This view is causing issues when optimizing requires constraints
   for other views, due to its structure (mapping non-overlapping containers)

## Why is this important?
These views will have suboptimal query performance that CANNOT be fixed by
adding or removing requires constraints. The only solutions require restructuring:
- Add a view-specific container that requires all the other containers in the view
- Restructure the view to use different containers

## Example
View `MultipleEquipments` maps only to containers `Valve` and `InstrumentEquipment`.
The optimal constraints are `Valve → CogniteEquipment` and `InstrumentEquipment → CogniteEquipment`
due to other views needing these constraints to optimize their query performance.
This means however, that neither Valve nor InstrumentEquipment can reach each other without
creating complex ingestion dependencies. The view needs a new container or restructuring.