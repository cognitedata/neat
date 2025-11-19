Validates that data model has a human-readable description.

## What it does
Validates that the data model has a human-readable description.

## Why is this bad?
A missing description makes it harder for users (humans or machines) to understand the purpose and scope
of the data model. The description provides important context about what domain the data model covers,
what use cases it supports, and how it should be used.

## Example
A data model has an id CIM, with name Common Information Model, but no description. Users may find it difficult to
understand what this data model represents, unless extra context is provided. In this particualar case, name
does not provide sufficient information, as it is too generic, that this data model is focused on the
electrical power systems domain. However, providing a description such as:
"The Common Information Model (CIM) is a standard developed by IEC for representing power system
components and their relationships. It is widely used in the electrical utility industry for data
exchange and system modeling." would greatly improve clarity and usability.