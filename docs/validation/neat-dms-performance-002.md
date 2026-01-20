Recommends removing requires constraints that are not part of the structure
considered optimal for query performance by Neat.

## What it does
Identifies existing requires constraints that are not optimal. These constraints
can be safely removed as they don't contribute to query optimization when all other
optimal constraints are applied.

## Why is this important?
Unnecessary requires constraints can:
- Create unnecessary ingestion dependencies
- Cause invalid requires constraint cycles if optimal constraints are applied

## Example
Container `Tag` has a `requires` constraint to `Pump`, but NEAT determined that
`Pump → Tag` is more optimal. The existing `Tag → Pump` constraint should then
be removed when applying all optimal constraints.