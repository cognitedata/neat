Validates that an enumeration has a human-readable name.

## What it does
Validates that each enumeration value in the data model has a human-readable name.

## Why is this bad?
A missing name makes it harder for users (humans or machines) to understand the purpose of the enumeration value.
This is important as enumeration values are often technical codes or abbreviations, and a clear name improves
usability, maintainability, searchability, and AI-readiness.

## Example
An enumeration value with id "NOM" in a wind turbine operational mode property has no name. Users may find it
difficult to understand what this value represents. Adding name "Normal Operation" would increase clarity
and usability.