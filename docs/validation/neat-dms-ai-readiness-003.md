Validates that a View has a human-readable name.

## What it does
Validates that each view in the data model has a human-readable name.

## Why is this bad?
A missing name makes it harder for users (humans or machines) to understand the purpose of the view.
This is important as views' external ids are often based on technical identifiers, abbreviations, etc.
Providing a clear name improves usability, maintainability, searchability, and AI-readiness.

## Example
A view has an id CFIHOS-30000038 but no name. Users may find it difficult to understand what this view represents,
unless they look up the id in documentation or other resources. Adding name "Pump" would increase clarity and
usability.