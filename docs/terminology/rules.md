# Rules
`Rules` is the core object in NEAT, which contains semantic data model definitions and optionally instructions on how
to create the data model instances (aka, populate data model). This object is typically serialized as a spreadsheet
file (Excel) which provides a simple and intuitive way to create a semantic data model. The spreadsheet obeys specific
template, which represents the `Rules` object. The template is designed to be user-friendly and to provide a simple
way to define a semantic data model, offering a familiar environment for users who are not
familiar with semantic data modeling.

To lower the entry barrier for the users, `Rules` are designed to be as simple as possible and profiled based on the
role that a person has in the data modeling process. Consider consulting [the data modeling lifecycle tutorial](../tutorials/data-modeling-lifecycle/overview.md)
for more detail on the process. The profiles are:

- Domain Expert
- Information Architect
- DMS CDF Architect

The level of details that are requested from the user grows with the role that the user has in the data modeling process.
Accordingly, we will dive into the details of the `Rules` object per role in the following sections,
which will be presented through the spreadsheet serialization of the `Rules` object.

`Rules` are composed of the following sheets, which based on the role (profile) are mandatory and/or optional
or require various levels of details:

- `Metadata`: contains metadata about the data model and how **NEAT** should validate it.
- `Classes`: contains the high-level definition of the classes that are part of the semantic data model (no properties)
- `Properties`: contains the definition of the properties per class
- `Views`: contains the definition of the CDF views that represent semantic data model serialization in CDF
- `Containers`: contains the definition of the CDF containers that are physical storage for data written/read in/from views
- `Prefixes`: contains the definition of the prefixes that are used in the semantic data model

The spreadsheet templates for the `Rules` object per role are accessible through the following links:

- [Domain Expert Rules Template](../artifacts/rules/domain-expert-rules-template.xlsx)
- [Information Architect Rules Template](../artifacts/rules/information-architect-rules-template.xlsx)
- [DMS CDF Architect Rules Template](../artifacts/rules/dms-architect-rules-template.xlsx)

In addition, a semantic data model may relate to other semantic data models, for example, a previous iteration
of the same data model or a data model that is the basis for the current data model. In such cases, there will be
multiple sets of `Rules` objects. In a spreadsheet serialization, the different `Rules` object are distinguished by
a prefix in the sheet name. The following prefixes are used:

* **No prefix**: The main `Rules`, object often referred to as the `user` or `current` `Rules` object.
* **`Last`**: The previous iteration of the `user` `Rules` object.
* **`Ref`**: (short for Reference) A `Rules` object that is referenced by the `user` `Rules` object.

For more information about how these different `Rules` objects are used, see the [Rules Validation](rules-validation.md).

## Metadata sheet

=== "Domain Expert Profile"

    | Field   | Description                                       | Predefined Value | Mandatory |
    |---------|---------------------------------------------------|------------------|-----------|
    | role    | Role of the person                                | `domain expert`  | Yes       |
    | creator | Names of data model creators separated with comma |                  | Yes       |

    !!! tip annotate "Usage"
        More details on **Domain Expert** Profile **Metadata sheet** usage can be found [here](../tutorials/data-modeling-lifecycle/part-1-knowledge-acquisition.md#domain-expert-metadata-anchor)!



=== "Information Architect Profile"

    | Field         | Description                                                      | Predefined Value                    | Mandatory |
    |---------------|------------------------------------------------------------------|-------------------------------------|-----------|
    | role          | The role of the person                                           | `domain expert`                     | Yes       |
    | creator       | Names of data model creators separated with comma                |                                     | Yes       |
    | schema        | Indication of the data model completeness                        | `complete`, `partial` or `extended` | Yes       |
    | dataModelType | data model type, two options enterprise or solution              | `enterprise` or `solution`          | Yes       |
    | extension     | Only relevant if schema=exented, indicates type of extension     | `addition`, `reshape` or `rebuild`  | No        |
    | namespace     | Data model namespace provided as URI                             |                                     | Yes       |
    | prefix        | Data model prefix which is used as a short form of the namespace |                                     | Yes       |
    | version       | Version of the data model                                        |                                     | Yes       |
    | created       | Date model creation date                                         |                                     | Yes       |
    | updated       | Date model last update date                                      |                                     | Yes       |
    | title         | Title of the data model                                          |                                     | No        |
    | description   | Short description of the data model                              |                                     | No        |
    | license       | License of the data model                                        |                                     | No        |
    | rights        | Usage right of the data model                                    |                                     | No        |

    !!! tip annotate "Usage"
        More details on **Information Architect** Profile **Metadata sheet** usage can be found [here](../tutorials/data-modeling-lifecycle/part-1-knowledge-acquisition.md#information-architect-metadata-sheet)!



=== "DMS CDF Architect Profile"

    | Field         | Description                                                     | Predefined Value                    | Mandatory |
    |---------------|-----------------------------------------------------------------|-------------------------------------|-----------|
    | role          | The role of the person                                          | `dms expert`                        | Yes       |
    | creator       | Names of data model creators separated with comma               |                                     | Yes       |
    | dataModelType | data model type, two options enterprise or solution             | `enterprise` or `solution`          | Yes       |
    | schema        | Indication of schema completeness                               | `complete`, `partial` or `extended` | Yes       |
    | extension     | Only relevant if schema=exented, indicates type of extension.   | `addition`, `reshape` or `rebuild`  | No        |
    | space         | CDF space to which data model belongs                           |                                     | Yes       |
    | externalId    | External id used to uniquely identify data model within a space |                                     | Yes       |
    | version       | Version of the data model                                       |                                     | Yes       |
    | created       | Date model creation date                                        |                                     | Yes       |
    | updated       | Date model last update date                                     |                                     | Yes       |
    | name          | Name  of the data model                                         |                                     | No        |
    | description   | Short description of the data model                             |                                     | No        |

    !!! tip annotate "Usage"
        More details on **DMS Architect** Profile **Metadata sheet**  usage can be found [here](../tutorials/data-modeling-lifecycle/part-1-knowledge-acquisition.md#changing-the-metadata-sheet)!

!!! tip annotate "Usage"
    For a more detailed explanation of the `dataModelType`, `schema` and `extension` see [Rules Validation](rules-validation.md).

!!! tip annotate "Usage"
    In addition, the `schema` and `extension` controls how [excel rules are inputted](rules-excel-input.md).


## Classes sheet

=== "Domain Expert Profile"

    The class sheet is not mandatory for the domain expert profile, but if used should follow the Information Architect profile `Classes` sheet.

=== "Information Architect Profile"

    | Column       | Description                                                    | Predefined Value     | Mandatory |
    |--------------|----------------------------------------------------------------|----------------------|-----------|
    | Class        | Class id being defined, use strongly advise `PascalCase` usage |                      | Yes       |
    | Name         | Human readable name of the class                               |                      | No        |
    | Description  | Short description of the class                                 |                      | Yes       |
    | Parent Class | Parent class id, used for property inheritance                 |                      | No        |
    | Reference    | Reference to the source of the class provided as `URI`         |                      | No        |
    | Match Type   | The match type between the source entity and the class         | `exact` or `partial` | No        |

    !!! tip annotate "Usage"
        More details on **Information Architect** Profile **Classes sheet**  usage can be found [here](../tutorials/data-modeling-lifecycle/part-1-knowledge-acquisition.md#information-architect-classes-sheet)!


## Properties sheet

=== "Domain Expert Profile"

    | Column      | Description                                                                                                                                                                        | Predefined Value      | Mandatory |
    |-------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------|-----------|
    | Class       | Class id that the property is defined for, strongly advise `PascalCase` usage                                                                                                      |                       | Yes       |
    | Property    | Property id, strongly advised to `camelCase` usage                                                                                                                                 |                       | Yes       |
    | Name        | Human readable name of the property                                                                                                                                                |                       | No        |
    | Description | Short description of the property                                                                                                                                                  |                       | Yes       |
    | Value Type  | Value type that the property can hold. It takes either subset of XSD type (see note below) or a class defined                                                                      | XSD Types or Class id | Yes       |
    | Min Count   | Minimum number of values that the property can hold. If no value is provided, the default value is  `0`, which means that the property is optional.                                |                       | Yes       |
    | Max Count   | Maximum number of values that the property can hold. If no value is provided, the default value is  `inf`, which means that the property can hold any number of values (listable). |                       | Yes       |

    <a id="xsd-type-anchor"></a>
    !!! info annotate "XSD Value Types"
        The following XSD types are supported:
        `boolean`, `float`, `double` ,`integer` ,`nonPositiveInteger` ,`nonNegativeInteger` ,`negativeInteger` ,`long` ,`string` ,`langString` ,`anyURI` ,`normalizedString` ,`token` ,`dateTime` ,`dateTimeStamp`  and `date`.
        In addition to the subset of XSD types, the following value types are supported:
        `timeseries`, `file` , `sequence` and `json`

    !!! tip annotate "Usage"
        More details on **Domain Expert** Profile **Properties sheet**  usage can be found [here](../tutorials/data-modeling-lifecycle/part-1-knowledge-acquisition.md#domain-expert-properties)!

=== "Information Architect Profile"

    | Column      | Description                                                                                                                                                                        | Predefined Value                   | Mandatory |
    |-------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------|-----------|
    | Class       | Class id that the property is defined for, strongly advise `PascalCase` usage                                                                                                      |                                    | Yes       |
    | Property    | Property id, strongly advised to `camelCase` usage                                                                                                                                 |                                    | Yes       |
    | Name        | Human readable name of the property                                                                                                                                                |                                    | No        |
    | Description | Short description of the property                                                                                                                                                  |                                    | Yes       |
    | Value Type  | Value type that the property can hold. It takes either subset of XSD type (see note below) or a class defined                                                                      | XSD Types or Class id              | Yes       |
    | Min Count   | Minimum number of values that the property can hold. If no value is provided, the default value is  `0`, which means that the property is optional.                                |                                    | Yes       |
    | Max Count   | Maximum number of values that the property can hold. If no value is provided, the default value is  `inf`, which means that the property can hold any number of values (listable). |                                    | Yes       |
    | Default     | Specifies default value for the property.                                                                                                                                          |                                    | No        |
    | Rule Type   | The rule type that is used to populate the data model                                                                                                                              | `sparql`, `rdfpath` or `rawlookup` | No        |
    | Rule        | The rule that is used to populate the data model. The rule is provided as a string, which is either SPARQL query or RDFPath query or RAW lookup query                              |                                    | No        |
    | Reference   | Reference to the source of the property provided as `URI`                                                                                                                          |                                    | No        |
    | Match Type  | The match type between the source entity and the class                                                                                                                             | `exact` or `partial`               | No        |

    !!! info annotate "XSD Value Types"
        The following XSD types are supported:
        `boolean`, `float`, `double` ,`integer` ,`nonPositiveInteger` ,`nonNegativeInteger` ,`negativeInteger` ,`long` ,`string` ,`langString` ,`anyURI` ,`normalizedString` ,`token` ,`dateTime` ,`dateTimeStamp`  and `date`.
        In addition to the subset of XSD types, the following value types are supported:
        `timeseries`, `file` , `sequence` and `json`

    !!! info annotate "Data model population rule"
        The `Rule Type` and `Rule` columns are used to populate the data model using [NEAT graph store](./graph.md).
        They are optional, but if used, both must be provided !

    !!! tip annotate "Usage"
        More details on **Information Architect** Profile **Properties sheet**  usage can be found [here](../tutorials/data-modeling-lifecycle/part-1-knowledge-acquisition.md#information-architect-properties)!



=== "DMS CDF Architect Profile"

    | Column             | Description                                                                                                                      | Predefined Value                          | Mandatory |
    |--------------------|----------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------|-----------|
    | Class (linage)     | Class id that the property is defined for, strongly advise PascalCase usage                                                      |                                           | Yes       |
    | Property (linage)  | Property id, strongly advised to camelCase usage                                                                                 |                                           | Yes       |
    | Name               | Human readable name of the property                                                                                              |                                           | No        |
    | Description        | Short description of the property                                                                                                |                                           | Yes       |
    | Value Type         | Value type that the property can hold. It takes either subset of CDF primitive types (see note below) or a View id (== Class id) | CDF Primitive Types of ViewID/ClassID     | Yes       |
    | Connection         | Only applies to relationships between classes (== views). It specify how relationship should be implemented in CDF.              | `direct`, `edge`, or `reverse`            | No        |
    | Nullable           | Used to indicate whether the property is required or not. Only applies to primitive type.                                        |                                           | No        |
    | Is List            | Used to indicate whether the property holds single or multiple values (list). Only applies to primitive types                    |                                           | No        |
    | Default            | Specifies default value for the property.                                                                                        |                                           | No        |
    | Reference          | Reference to the source of the property provided as `URI`                                                                        |                                           | No        |
    | Match Type         | The match type between the source entity and the class                                                                           | `exact` or `partial`                      | No        |
    | Container          | Specifies container in which instances of given class/view are being stored in                                                   |                                           | No        |
    | Container Property | Specifies under which property instances of given class/view property are being stored under                                     |                                           | No        |
    | Index              | The name of the index the property is part of                                                                                    |                                           | No        |
    | Constraints        | Constraint for given property                                                                                                    |                                           | No        |
    | View               | View id to which property is being defined for                                                                                   |                                           | Yes       |
    | View Property      | View property for which property is being defined for                                                                            |                                           | Yes       |

    !!! info annotate "CDF Primitive Types"
        The following CDF primitive types are supported:
        `boolean`,`float32`,`float64`,`int32`,`int64`,`text`,`timestamp`,`timeseries`,`file`,`sequence`,`json``token` ,`dateTime` ,`dateTimeStamp`  and `date`.

    !!! tip annotate "Usage"
        More details on **DMS Architect** Profile **Properties sheet**  usage can be found [here](../tutorials/data-modeling-lifecycle/part-1-knowledge-acquisition.md#dms-architect-properties)!

    !!! tip annotate "Details"
        More details can be found [here](dmsrules.md#properties)!


## Views sheet
This sheet is only used for the DMS/CDF Architect, and it is mandatory. The sheet should have the following columns:

| Column         | Description                                                                                                        | Predefined Value          | Mandatory |
|----------------|--------------------------------------------------------------------------------------------------------------------|---------------------------|-----------|
| Class (linage) | Class id, originally coming from Information Architect sheet, used for linage. strongly advised to PascalCase usage|                           | Yes       |
| View           | View id, strongly advised to PascalCase usage                                                                      |                           | Yes       |
| Name           | Human readable name of the view being defined                                                                      |                           | No        |
| Description    | Short description of the view being defined                                                                        |                           | Yes       |
| Implements     | List of parent view ids which the view being defined implements                                                    |                           | No        |
| Filter         | Filter(s) which the view being defined should use                                                                  | `hasData`, `nodeType`, '' | No        |
| In Model       | Indicates whether the view being defined is a part of the data model                                               | `True`, `False`           | No        |


!!! tip annotate "Usage"
    More details on **DMS Architect** Profile **Views sheet**  usage can be found [here](../tutorials/data-modeling-lifecycle/part-1-knowledge-acquisition.md#dms-architect-views-sheet)!

!!! tip annotate "Details"
    More details can be found [here](dmsrules.md#view)!

## Containers sheet
This sheet is only used for the DMS/CDF Architect, and it is optional. The sheet should have the following columns:

| Column         | Description                                                                                                        | Predefined Value              | Mandatory |
|----------------|--------------------------------------------------------------------------------------------------------------------|-------------------------------|-----------|
| Class (linage) | Class id, originally coming from Information Architect sheet, used for linage. strongly advised to PascalCase usage|                               | Yes       |
| Container      | Container id, strongly advised to PascalCase usage                                                                 |                               | Yes       |
| Name           | Human readable name of the container being defined                                                                 |                               | No        |
| Description    | Short description of the view being defined                                                                        |                               | No        |
| Constraint     | Constraint to be applied on the container being defined                                                            |                               | No        |


!!! tip annotate "Usage"
    More details on **DMS Architect** Profile **Containers sheet**  usage can be found [here](../tutorials/data-modeling-lifecycle/part-1-knowledge-acquisition.md#dms-architect-containers-sheet)!


## Prefixes sheet
The `Prefixes` sheet is only used for the Information Architect profile when there is a need to specify the prefixes that are used in the semantic data model. The sheet should have the following columns:

| Column    | Description                                                                 |Predefined Value | Mandatory |
|-----------|-----------------------------------------------------------------------------|-----------------|-----------|
| Prefix    | Prefix that is used in the semantic data model                              |                 | Yes       |
| Namespace | Namespace that the prefix represents provided as `URI`                      |                 | Yes       |
