Validates that source property for the reverse connections is a direct relation.

## What it does
Checks that the property referenced in a reverse connection's 'through' clause
is actually a direct connection property (not a primitive, edge, or reverse relation).

## Why is this bad?
Reverse connections can only work with direct connection properties.
Using other property types breaks the bidirectional relationship. Pointing through
another reverse direct relation never resolves to container storage, even when
containers have correct direct relation properties defined.

## Example
If WindFarm has a reverse property `turbines` through `WindTurbine.name`,
but `name` is a Text property (not a direct connection), the reverse connection is invalid.
If ViewA's reverse property points through ViewB's reverse property instead of a direct
relation, neither reverse connection maps down to a container.