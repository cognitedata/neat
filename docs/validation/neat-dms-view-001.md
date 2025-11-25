Validates that container and container property referenced by view property exist.

## What it does
Validates that for each view property that maps to a container and container property,
the referenced container and container property exist.

## Why is this bad?
If a view property references a container or container property that does not exist,
the data model cannot be deployed to CDF. This means that view property will not be able to function.

## Example
View WindTurbine has property location that maps to container WindTurbineContainer and property gpsCoordinates.
If WindTurbineContainer and/or property gpsCoordinates does not exist, the data model cannot be deployed to CDF.