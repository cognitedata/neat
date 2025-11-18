Validates that connection value types exist.

## What it does
Validates that all connection value types defined in the data model exist.

## Why is this bad?
If a connection value type does not exist, the data model cannot be deployed to CDF.
This means that the connection will not be able to function.

## Example
If view WindTurbine has a connection property windFarm with value type WindFarm, but WindFarm view is not defined,
the data model cannot be deployed to CDF.