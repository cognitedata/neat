Validates that a view does not reference too many containers.

## What it does
Checks that the view references no more containers than the CDF limit allows.

## Why is this bad?
Mapping too many containers to a single view can lead to performance issues to increasing number of joins
that need to be performed when querying data through the view.

## Example
If a view references 20 containers and the CDF limit is 10 containers per view,
this validator will raise a Recommendation.