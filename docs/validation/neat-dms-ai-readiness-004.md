Validates that a View has a human-readable description.

## What it does
Validates that each view in the data model has a human-readable description.

## Why is this bad?
A missing description makes it harder for users (humans or machines) to understand in what context the view
should be used. The description can provide important information about the view's purpose, scope, and usage.


## Example
A view Site has no description. Users may find it difficult to understand what this view represents, unless
extra context is provided. Even if we know that Site is used in the context of wind energy developments, a
description is necessary as it can be used in various context within the same domain such as:

Option 1 — Project area
This view represents a geographical area where wind energy projects are developed and managed.

Option 2 — Lease area
The legally defined lease area allocated for offshore wind development.

Option 3 — Measurement site
A specific location where wind measurements (e.g., LiDAR, met mast) are collected.