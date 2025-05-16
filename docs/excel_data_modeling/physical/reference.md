# Physical Reference

This document is a reference for the physical data model. It was last generated 2025-05-15.

The physical data model has the following sheets:
- Metadata: Contains information about the data model.
- Properties: Contains the properties of the data model.
- Views: Contains the views of the data model.
- Containers (optional): Contains the definition containers that are the physical storage of the data model.
- Enum (optional): Contains the definition of enum values.
- Nodes (optional): Contains the definition of the node types.

## Metadata Sheet

Contains information about the data model.

| Field | Description | Mandatory |
|----------------|-------------|-----------|
| space | The space where the data model is defined | Yes |
| externalId | External identifier for the data model | Yes |
| version | Version of the data model | Yes |
| name | Human readable name of the data model | No |
| description | Short description of the data model | No |
| creator | List of creators (comma separated) to the data model. | Yes |
| created | Date of the data model creation | Yes |
| updated | Date of the data model update | Yes |
| sourceId | Id of source that produced this data model | No |
| conceptual | None | No |

## Properties Sheet

Contains the properties of the data model.

| Column Name | Description | Mandatory |
|----------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| View | The property identifier. | Yes |
| View Property | The ViewId this property belongs to | Yes |
| Name | Human readable name of the property | No |
| Description | Short description of the property | No |
| Connection | nly applies to connection between views. It specify how the connection should be implemented in CDF. | No |
| Value Type | Value type that the property can hold. It takes either subset of CDF primitive types or a View id | Yes |
| Min Count | Minimum number of values that the property can hold. If no value is provided, the default value is  `0`, which means that the property is optional. | No |
| Max Count | Maximum number of values that the property can hold. If no value is provided, the default value is  `inf`, which means that the property can hold any number of values (listable). | No |
| Immutable | sed to indicate whether the property is can only be set once. Only applies to primitive type. | No |
| Default | Specifies default value for the property. | No |
| Container | Specifies container where the property is stored. Only applies to primitive type. | No |
| Container Property | Specifies property in the container where the property is stored. Only applies to primitive type. | No |
| Index | The names of the indexes (comma separated) that should be created for the property. | No |
| Constraint | List of creators (comma separated) to the data model.. | No |
| Conceptual | Used to make connection between physical and conceptual data model aspect | No |

## Views Sheet

Contains the views of the data model.

| Column Name | Description | Mandatory |
|----------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| View | View id, strongly advised to PascalCase usage. | Yes |
| Name | Human readable name of the view being defined. | No |
| Description | Short description of the view being defined  | No |
| Implements | List of parent view ids (comma separated) which the view being defined implements. | No |
| Filter | Explicitly define the filter for the view. | No |
| In Model | Indicates whether the view being defined is a part of the data model. | Yes |
| Conceptual | Used to make connection between physical and conceptual data model level | No |

## Containers Sheet

Contains the definition containers that are the physical storage of the data model.

| Column Name | Description | Mandatory |
|----------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| Container | Container id, strongly advised to PascalCase usage. | Yes |
| Name | Human readable name of the container being defined. | No |
| Description | Short description of the node being defined. | No |
| Constraint | List of required (comma separated) constraints for the container | No |
| Used For |  Whether the container is used for nodes, edges or all. | Yes |

## Enum Sheet

Contains the definition of enum values.

| Column Name | Description | Mandatory |
|----------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| Collection | The collection this enum belongs to. | Yes |
| Value | The value of the enum. | Yes |
| Name | Human readable name of the enum. | No |
| Description | Short description of the enum. | No |

## Nodes Sheet

Contains the definition of the node types.

| Column Name | Description | Mandatory |
|----------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| Node | The type definition of the node. | Yes |
| Usage | What the usage of the node is in the data model. | Yes |
| Name | Human readable name of the node being defined. | No |
| Description | Short description of the node being defined. | No |
