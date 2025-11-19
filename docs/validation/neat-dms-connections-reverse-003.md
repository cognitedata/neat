Validates that source property for the reverse connections is a direct relation.

## What it does
Checks that the property referenced in a reverse connection's 'through' clause
is actually a direct connection property (not a primitive or other type).

## Why is this bad?
Reverse connections can only work with direct connection properties.
Using other property types breaks the bidirectional relationship.

## Example
If WindFarm has a reverse property `turbines` through `WindTurbine.name`,
but `name` is a Text property (not a direct connection), the reverse connection is invalid.