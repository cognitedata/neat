Validates that an enumeration value has a human-readable description.

## What it does
Validates that each enumeration value in the data model has a human-readable description.

## Why is this bad?
A missing description makes it harder for users (humans or machines) to understand the meaning and context
of the enumeration value. The description can provide important information about when and how the value
should be used, especially when enumeration values are technical codes or abbreviations.

## Example
An enumeration value "NOM" in a wind turbine operational mode property has no description. Users may find it
difficult to understand what this value represents without additional context. Even with a name like
"Normal Operation", the description is valuable as it can clarify specifics:

Option 1 — Basic definition
The turbine is operating normally and generating power according to its power curve.

Option 2 — Detailed operational context
The turbine is in normal operation mode, actively generating power with all systems functioning within
specified parameters and connected to the grid.

Option 3 — Contrasting with other modes
Standard operating mode where the turbine follows the power curve and responds to grid commands,
as opposed to maintenance mode or fault conditions.