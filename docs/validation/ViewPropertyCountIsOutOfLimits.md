Validates that a view does not exceed the maximum number of properties.

## What it does
Checks that the view has no more properties than the CDF limit allows.

## Why is this bad?
CDF enforces limits on the number of properties per view to ensure optimal performance.

## Example
If a view has 150 properties and the CDF limit is 100 properties per view,
this validator will raise a ConsistencyError issue.