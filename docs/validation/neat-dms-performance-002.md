Recommends removing requires constraints that are not part of the optimal structure.

## What it does
Identifies existing requires constraints that are not part of ANY view's optimal
MST structure. These constraints can be safely removed as they don't contribute
to query optimization.

## Why is this important?
Unnecessary requires constraints can:
- Create false ingestion dependencies
- Make the data model harder to understand
- Potentially cause issues if the constraint becomes invalid

## Example
Container `Pump` has `requires: Tag`, but the optimal MST determined that
`Pump → CogniteAsset` (which transitively covers Tag) is better.
The `Pump → Tag` constraint can be removed.