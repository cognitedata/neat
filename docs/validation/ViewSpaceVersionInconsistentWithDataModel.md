Validates that views have consistent space and version with the data model.

## What it does
Validates that all views in the data model have the same space and version as the data model.

## Why is this bad?
If views have different space or version than the data model, it may lead to more demanding development and
maintenance efforts. The industry best practice is to keep views in the same space and version as the data model.

## Example
If the data model is defined in space "my_space" version "v1", but a view is defined in the same spave but with
version "v2", this requires additional attention during deployment and maintenance of the data model.