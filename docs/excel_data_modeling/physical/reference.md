# Physical Reference

This document is a reference for the physical data model. It was last generated 2024-12-06.

The physical data model has the following sheets:
- Metadata: Contains information about the data model.
- Properties: Contains the properties of the data model.
- Views: Contains the views of the data model.
- Containers (optional): Contains the definition containers that are the physical storage of the data model.
- Enum (optional): Contains the definition of enum values.
- Nodes (optional): Contains the definition of the node types.

## Metadata Sheet

Contains information about the data model.

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
| logical | None | No |

## Properties Sheet

Contains the properties of the data model.

| Column Name | Description | Mandatory |
|-------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| View | None | Yes |
| View Property | None | Yes |
| Name | None | No |
| Description | None | No |
| Connection | None | No |
| Value Type | None | Yes |
| Nullable | None | No |
| Immutable | None | No |
| Is List | None | No |
| Default | None | No |
| Container | None | No |
| Container Property | None | No |
| Index | None | No |
| Constraint | None | No |
| Logical | Used to make connection between physical and logical data model aspect | No |

## Views Sheet

Contains the views of the data model.

| Column Name | Description | Mandatory |
|-------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| View | None | Yes |
| Name | None | No |
| Description | None | No |
| Implements | None | No |
| Filter | None | No |
| In Model | None | Yes |
| Logical | Used to make connection between physical and logical data model aspect | No |

## Containers Sheet

Contains the definition containers that are the physical storage of the data model.

| Column Name | Description | Mandatory |
|-------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| Container | None | Yes |
| Name | None | No |
| Description | None | No |
| Constraint | None | No |
| Used For | None | Yes |

## Enum Sheet

Contains the definition of enum values.

| Column Name | Description | Mandatory |
|-------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| Collection | None | Yes |
| Value | None | Yes |
| Name | None | No |
| Description | None | No |

## Nodes Sheet

Contains the definition of the node types.

| Column Name | Description | Mandatory |
|-------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| Node | None | Yes |
| Usage | None | Yes |
| Name | None | No |
| Description | None | No |
