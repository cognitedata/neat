Validates that the data model does not exceed the maximum number of views.

## What it does
This validator checks that the total number of views referenced by the data model
does not exceed the limit defined in the CDF project.

## Why is this bad?
CDF enforces limits on the number of views per data model to ensure optimal performance
and resource utilization.

## Example
If the CDF project has a limit of 100 views per data model, and the data model
references 120 views, this validator will raise a ConsistencyError issue.