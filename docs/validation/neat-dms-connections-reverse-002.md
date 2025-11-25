Validates that source property referenced in reverse connections exist.

## What it does
Checks that the direct connection property in the source view (used in the reverse connection's 'through')
actually exists in the source view.

## Why is this bad?
A reverse connection requires a corresponding direct connection property in the source view.
If this property doesn't exist, the bidirectional connection is incomplete.

## Example
If WindFarm has a reverse property `turbines` through `WindTurbine.windFarm`,
but WindTurbine view doesn't have a `windFarm` property, the reverse connection is invalid.