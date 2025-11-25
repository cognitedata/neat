Validates that data model has a human-readable name.

## What it does
Validates that the data model has a human-readable name.

## Why is this bad?
Often the data model ids are technical identifiers, abbreviations, etc.
A missing name makes it harder for users (humans or machines) to understand what the data model represents.
Providing a clear name improves usability, maintainability, searchability, and AI-readiness.

## Example
A data model has an id IEC61400-25-2 but no name. Users may find it difficult to understand what this data model
represents. However adding a name "Wind Energy Information Model" would increase clarity and usability.