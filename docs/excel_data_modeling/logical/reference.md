# Logical Reference

This document is a reference for the logical data model. It was last generated 2024-12-06.

The logical data model has the following sheets:
- Metadata: None
- Properties: None
- Classes: None
- Prefixes: None

## Metadata Sheet

None

| Column Name | Description | Mandatory |
|-------------|-------------|-----------|
| prefix | None | Yes |
| externalId | None | Yes |
| version | None | Yes |
| name | Human readable name of the data model | No |
| description | None | No |
| creator | List of contributors to the data model creation, typically information architects are considered as contributors. | Yes |
| created | Date of the data model creation | Yes |
| updated | Date of the data model update | Yes |
| physical | Link to the physical data model aspect | No |
| conceptual | Link to the conceptual data model aspect | No |

## Properties Sheet

None

| Column Name | Description | Mandatory |
|-------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| Class | None | Yes |
| Property | None | Yes |
| Name | None | No |
| Description | None | No |
| Value Type | None | Yes |
| Min Count | None | No |
| Max Count | None | No |
| Default | None | No |
| Transformation | None | No |
| Inherited | Flag to indicate if the property is inherited, only use for internal purposes | Yes |
| physical | Link to the class representation in the physical data model aspect | No |
| conceptual | Link to the conceptual data model aspect | No |

## Classes Sheet

None

| Column Name | Description | Mandatory |
|-------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| Class | None | Yes |
| Name | None | No |
| Description | None | No |
| Implements | None | No |
| physical | Link to the class representation in the physical data model aspect | No |
| conceptual | Link to the conceptual data model aspect | No |
