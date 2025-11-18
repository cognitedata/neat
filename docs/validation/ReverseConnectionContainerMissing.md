Validates that the container referenced by the reverse connection source properties exist.

## What it does
Checks that the container holding the direct connection property (used in reverse connection) exists.

## Why is this bad?
The direct connection property must be stored in a container.
If the container doesn't exist, the connection cannot be persisted.

## Example
If WindTurbine.windFarm maps to container `WindTurbine`, but this container doesn't exist,
the reverse connection from WindFarm cannot function.