Validates that a View property has a human-readable description.

## What it does
Validates that each view property in the data model has a human-readable description.

## Why is this bad?
A missing description makes it harder for users (humans or machines) to understand in what context the view property
should be used. The description can provide important information about the view property's purpose,
scope, and usage.


## Example
A view WindTurbine has a property status with no description. Users may find it difficult to understand what this
property represents, unless extra context is provided. Even if we know that status is related to wind turbine
operations, a description is necessary as it can have different meanings in various contexts:

Option 1 — Operational status
Current operational state of the wind turbine (e.g., running, stopped, maintenance, fault).

Option 2 — Connection status
Grid connection status indicating whether the turbine is connected to the electrical grid.

Option 3 — Availability status
Availability state for production indicating whether the turbine is available for power generation.