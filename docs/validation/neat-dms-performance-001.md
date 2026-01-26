Recommends adding requires constraints to optimize query performance.

## What it does
Identifies views that is mapping to containers where adding a requires constraint,
would improve query performance. The recommendation message indicates whether the
change is "safe" or requires attention to potential ingestion dependencies.

## Why is this important?
Views without proper requires constraints may have poor query performance.
Adding requires constraints enables queries to perform under-the-hood optimizations.

## Example
View `Valve` is mapping to both containers `Valve` and `CogniteEquipment`.
A `requires` constraint from `Valve` to `CogniteEquipment` is likely needed
to enable efficient query performance.