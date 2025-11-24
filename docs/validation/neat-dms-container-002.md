Validates that any container property referenced by a view property, when the
referenced container does not belong to the data model's space, exists in CDF.

## What it does
For each view property that maps to a container in a different space than the data model,
this validator checks that the referenced container property exists in that external container in CDF.
This validator only runs if the external container exists in CDF.

## Why is this bad?
If a view property references a container property that does not exist in CDF,
the data model cannot be deployed. The affected view property will not function, and the
deployment of the entire data model will fail.

## Example
View `my_space:WindTurbine` has a property `location` that maps to container property
`gpsCoordinates` in `other_space:WindTurbineContainer`. If `gpsCoordinates` does not exist
in that container in CDF, deployment will fail.