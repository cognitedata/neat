Recommends removing requires constraints that are not optimal.

## What it does
Identifies existing requires constraints that are not optimal for querying purposes,
as they are either redundant or create unnecessary ingestion dependencies when all
other optimal constraints are applied. These constraints can be safely removed
without affecting query performance.

## Why is this important?
Unnecessary requires constraints can:
- Create unnecessary ingestion dependencies
- Cause invalid requires constraint cycles if optimal constraints are applied

## Example
Container `Tag` has a `requires` constraint to `Pump`, but NEAT determined that
`Pump → Tag` is more optimal. The existing `Tag → Pump` constraint should then
be removed when applying all optimal constraints.