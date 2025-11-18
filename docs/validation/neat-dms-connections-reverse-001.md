Validates that source view referenced in reverse connection exist.

## What it does
Checks that the source view used to configure a reverse connection exists.

## Why is this bad?
A reverse connection requires a corresponding direct connection in the source view.
If the source view doesn't exist, the reverse connection is invalid.

## Example
If WindFarm has a reverse property `turbines` through `WindTurbine.windFarm`,
but WindTurbine view doesn't exist, the reverse connection cannot function.