Validates that direct connections point to specific views rather than ancestors.

## What it does
Checks whether the direct connection property points to an ancestor of the expected target view
and recommends pointing to the specific target instead.

## Why is this bad?
While technically valid, pointing to ancestors can be confusing and may lead to mistakes.
It's clearer to point to the specific target view.

## Example
If WindFarm.turbines expects WindTurbine.windFarm to point to WindFarm,
but it points to Asset (ancestor of WindFarm), this validator recommends the change.