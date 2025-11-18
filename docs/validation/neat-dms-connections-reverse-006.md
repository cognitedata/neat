Validates that the container property used in reverse connection is the direct relations.

## What it does
Checks that the container property (mapped from view's direct connection property)
has type DirectNodeRelation.

## Why is this bad?
Container properties backing connection view properties must be DirectNodeRelation type.
Other types cannot represent connections in the underlying storage.

## Example
If WindTurbine.windFarm maps to container property with type Text instead of DirectNodeRelation,
the connection cannot be stored correctly.