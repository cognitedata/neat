# Conceptual Reference

This document is a reference for the conceptual data model. It was last generated 2025-05-15.

The conceptual data model has the following sheets:
- Metadata: Metadata for the conceptual data model
- Properties: List of properties
- Concepts: List of concepts
- Prefixes: the definition of the prefixes that are used in the conceptual data model

## Metadata Sheet

Metadata for the conceptual data model

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
| physical | Link to the physical data model level | No |

## Properties Sheet

List of properties

| Column Name | Description | Mandatory |
|----------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| Concept | Concept id that the property is defined for, strongly advise `PascalCase` usage. | Yes |
| Property | Property id, strongly advised to `camelCase` usage. | Yes |
| Name | Human readable name of the property. | No |
| Description | Short description of the property. | No |
| Value Type | Value type that the property can hold. It takes either subset of XSD type or a class defined. | Yes |
| Min Count | Minimum number of values that the property can hold. If no value is provided, the default value is  `0`, which means that the property is optional. | No |
| Max Count | Maximum number of values that the property can hold. If no value is provided, the default value is  `inf`, which means that the property can hold any number of values (listable). | No |
| Default | Default value of the property. | No |
| Instance Source | The URIRef(s) in the graph to get the value of the property. | No |
| Physical | Link to the class representation in the physical data model aspect | No |

## Concepts Sheet

List of concepts

| Column Name | Description | Mandatory |
|----------------|-------------|-----------|
| Neat ID | Globally unique identifier for the property | No |
| Concept | Concept id being defined, use strongly advise `PascalCase` usage. | Yes |
| Name | Human readable name of the class. | No |
| Description | Short description of the class. | No |
| Implements | List of classes (comma separated) that the current class implements (parents). | No |
| Instance Source | The link to to the rdf.type that have the instances for this class. | No |
| Physical | Link to the class representation in the physical data model aspect | No |
