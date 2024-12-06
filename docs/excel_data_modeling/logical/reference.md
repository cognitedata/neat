# Logical Reference

This document is a reference for the logical data model. It was last generated 2024-12-06.

The logical data model has the following sheets:
- Metadata: Metadata for the logical data model
- Properties: List of properties
- Classes: List of classes
- prefixes: the definition of the prefixes that are used in the semantic data model

## Metadata Sheet

Metadata for the logical data model

| Field | Description | Mandatory |
|----------------|-------------|-----------|
| space | The space where the data model is defined | Yes |
| externalId | External identifier for the data model | Yes |
| version | Version of the data model | Yes |
| name | Human readable name of the data model | No |
| description | Short description of the data model | No |
| creator | List of contributors (comma seperated) to the data model creation, typically information architects are considered as contributors. | Yes |
| created | Date of the data model creation | Yes |
| updated | Date of the data model update | Yes |
| physical | Link to the physical data model aspect | No |
| conceptual | Link to the conceptual data model aspect | No |

## Properties Sheet

List of properties

| Column Name | Description | Mandatory |
|----------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| Class | Class id that the property is defined for, strongly advise `PascalCase` usage. | Yes |
| Property | Property id, strongly advised to `camelCase` usage. | Yes |
| Name | Human readable name of the property. | No |
| Description | Short description of the property. | No |
| Value Type | Value type that the property can hold. It takes either subset of XSD type or a class defined. | Yes |
| Min Count | Minimum number of values that the property can hold. If no value is provided, the default value is  `0`, which means that the property is optional. | No |
| Max Count | Maximum number of values that the property can hold. If no value is provided, the default value is  `inf`, which means that the property can hold any number of values (listable). | No |
| Default | Default value of the property. | No |
| Transformation | The rule that is used to populate the data model. The rule is provided in a RDFPath query syntax which is converted to downstream solution query (e.g. SPARQL). | No |
| Inherited | Flag to indicate if the property is inherited, only use for internal purposes | Yes |
| physical | Link to the class representation in the physical data model aspect | No |
| conceptual | Link to the conceptual data model aspect | No |

## Classes Sheet

List of classes

| Column Name | Description | Mandatory |
|----------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| Class | Class id being defined, use strongly advise `PascalCase` usage. | Yes |
| Name | Human readable name of the class. | No |
| Description | Short description of the class. | No |
| Implements | List of classes (comma separated) that the current class implements (parents). | No |
| physical | Link to the class representation in the physical data model aspect | No |
| conceptual | Link to the conceptual data model aspect | No |
