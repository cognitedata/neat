Validates that any container or container property referenced by a view property, when the
referenced container does not belong to the data model's space, exists in CDF.

## What it does
For each view property that maps to a container in a different space than the data model,
this validator checks that:
- the referenced external container exists in CDF, and
- that the referenced container property also exists in that external container.

## Why is this bad?
If a view property references a container or container property that does not exist in CDF,
the data model cannot be deployed. The affected view property will not function, and the
deployment of the entire data model will fail.

## Example
View `my_space:WindTurbine` has a property `location` that maps to container
`other_space:WindTurbineContainer`, where `other_space` differs from `my_space`. If that
container does not exist in CDF, the model cannot be deployed.

Similarly, if a view property references `other_space:WindTurbineContainer` and its property
`gpsCoordinates`, and `gpsCoordinates` does not exist in that container in CDF, deployment
will also fail.