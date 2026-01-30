Recommends adding a cursorable index on direct relation properties that are
targets of reverse direct relations for query performance.

## What it does
Identifies direct relation properties that are referenced by reverse direct relations
but lack a cursorable B-tree index. When querying through a reverse direct relation,
CDF needs to look up nodes that have the direct relation pointing to the
source nodes. Without an index, this requires scanning many nodes inefficiently.

## Why is this important?
Traversing a reverse direct relation (inwards direction) requires an index on the
target direct relation property. Without this index, queries will be inefficient,
potentially leading to timeouts over time, as they won't scale well with data volume.

The exception is when the target direct relation is a list property. In that case,
this validator will not flag them, as reverse direct relations targeting lists of
direct relations needs to be traversed using the `instances/search` endpoint instead,
which does not directly benefit from adding indexes to container properties.

## Example
View `WindFarm` has a reverse property `turbines` through `WindTurbine.windFarm`.
Container `WindTurbine` should have a cursorable B-tree index on the `windFarm`
property to enable efficient traversal from WindFarm to its turbines.