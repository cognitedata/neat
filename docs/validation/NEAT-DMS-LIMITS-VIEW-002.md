Validates that a view does not reference too many containers.

## What it does
Checks that the view references no more containers than the CDF limit allows.

## Why is this bad?
CDF enforces limits on the number of containers per view to prevent overly complex view definitions, leading
to too many joins and performance degradation.

## Example
If a view references 20 containers and the CDF limit is 10 containers per view,
this validator will raise a ConsistencyError issue.