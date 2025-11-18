Validates that direct connections point to the correct target views.

## What it does
Checks that the direct connection property points to the expected target view
(the view containing the reverse connection).

## Why is this bad?
The reverse connection expects a bidirectional relationship.
If the direct connection points to a different view, the relationship is broken.

## Example
If WindFarm.turbines is a reverse through WindTurbine.windFarm,
but WindTurbine.windFarm points to SolarFarm instead of WindFarm, the connection is invalid.