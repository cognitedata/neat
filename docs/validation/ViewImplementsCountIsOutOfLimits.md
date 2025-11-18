Validates that a view does not implement too many other views.

## What it does
Checks that the view implements no more views than the CDF limit allows.

## Why is this bad?
CDF enforces limits on the number of implemented views to prevent overly deep inheritance hierarchies.

## Example
If a view implements 15 other views and the CDF limit is 10 implemented views per view,
this validator will raise a ConsistencyError issue.