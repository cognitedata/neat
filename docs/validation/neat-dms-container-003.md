Validates that any container required by another container exists in the data model.

## What it does
For each container in the data model, this validator checks that any container it
requires (via requires constraints) exists either in the data model or in CDF.

## Why is this bad?
If a container requires another container that does not exist in the data model or in CDF,
the data model cannot be deployed. The affected container will not function, and
the deployment of the entire data model will fail.

## Example
Container `windy_space:WindTurbineContainer` has a constraint requiring `windy_space:LocationContainer`.
If `windy_space:LocationContainer` does not exist in the data model or in CDF, deployment will fail.