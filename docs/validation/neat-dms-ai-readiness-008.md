Validates that an enumeration has a human-readable description.

## What it does
Validates that each enumeration in the data model has a human-readable description.

## Why is this bad?
A missing description makes it harder for users (humans or machines) to understand the purpose of the enumeration.
This is important as enumerations are often used to represent categorical data, and a clear description improves
usability, maintainability, searchability, and AI-readiness.

## Example
An enumeration with id WT-OP-MODE has no description. Users may find it difficult to understand what this enumeration
represents, unless they look up the id in documentation or other resources. Adding description such as
"Enumeration representing the different operational modes of a wind turbine, including normal operation,
maintenance mode, and fault conditions." would increase clarity and usability.