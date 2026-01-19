Recommends adding requires constraints to optimize query performance.

## What it does
Identifies views where adding a requires constraint would improve query performance.
The recommendation message indicates whether the change is "safe" (no cross-view
dependencies) or requires attention to ingestion order.

## Why is this important?
Views without proper requires constraints may have poor query performance.
Adding requires constraints creates a connected hierarchy that enables efficient queries.

## Example
View `Valve` needs `Tag → CogniteAsset` for optimization. The message will indicate
if other views using `Tag` will also be affected by this change.