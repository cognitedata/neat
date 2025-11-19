Validates that container property referenced by the reverse connections exists.

## What it does
Checks that the property in the container (mapped from the view's direct connection property)
actually exists in the container.

## Why is this bad?
The view property must map to an actual container property for data persistence.
If the container property doesn't exist, data cannot be stored.

## Example
If WindTurbine.windFarm maps to container property `WindTurbine.windFarm`,
but this container property doesn't exist, the connection cannot be stored.