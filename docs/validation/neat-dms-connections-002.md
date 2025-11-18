Validates that connection value types are not None, i.e. undefined.

## What it does
Validates that connections have explicitly defined value types (i.e., end connection node type).

## Why is this bad?
If a connection value type is None (undefined), there is no type information about the end node of the connection.
This yields an ambiguous data model definition, which may lead to issues during consumption of data from CDF.

## Example
Consider a scenario where we have views WindTurbine,ArrayCable and Substation. Lets say WindTurbine has a connection
`connectsTo` with value type None (undefined), then it is unclear what type of view the connection points to as
both ArrayCable and Substation are valid targets for the connection.