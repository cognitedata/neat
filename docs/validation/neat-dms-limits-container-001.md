Validates that a container does not exceed the maximum number of properties.

## What it does
Checks that the container has no more properties than the CDF limit allows.

## Why is this bad?
CDF enforces limits on the number of properties per container to ensure optimal performance
and prevent PostGres tables that have too many columns.

## Example
If a container has 150 properties and the CDF limit is 100 properties per container,
this validator will raise a ConsistencyError issue.