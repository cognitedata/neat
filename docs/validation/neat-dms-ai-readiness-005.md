Validates that a view property has a human-readable name.

## What it does
Validates that each view property in the data model has a human-readable name.

## Why is this bad?
A missing name makes it harder for users (humans or machines) to understand the purpose of the view property.
This is important as view property's ids are often based on technical identifiers, abbreviations, etc.
Providing a clear name improves usability, maintainability, searchability, and AI-readiness.

## Example
A view WindTurbine has a property pc which has no name. Users may find it difficult to understand what this view
property represents, unless they look up the id in documentation or other resources. Adding name "power curve"
would increase clarity and usability.