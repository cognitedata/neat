Validates that the direct connection in reverse connection pair have target views specified.

## What it does
Checks whether the direct connection property (referenced by reverse connection) has a value type.

## Why is this bad?
While CDF allows value type None as a SEARCH hack for multi-value relations,
it's better to explicitly specify the target view for clarity and maintainability.

## Example
If WindTurbine.windFarm has value type None instead of WindFarm,
this validator recommends specifying WindFarm explicitly.