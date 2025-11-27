Validates that an enumeration has a human-readable name.

## What it does
Validates that each enumeration in the data model has a human-readable name.

## Why is this bad?
A missing name makes it harder for users (humans or machines) to understand the purpose of the enumeration.
This is important as enumerations are often used to represent categorical data, and a clear name improves
usability, maintainability, searchability, and AI-readiness.

## Example
An enumeration with id WT-OP-MODE has no name. Users may find it difficult to understand what this enumeration
represents, unless they look up the id in documentation or other resources. Adding name "Wind Turbine Operation
Modes" would increase clarity and usability.