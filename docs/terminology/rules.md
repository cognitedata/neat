# Rules
`Rules` is the core object in NEAT, which contains semantic data model definitions and optionally instructions on how to create the data model instances (aka, populate data model). This object is typically serialized as an spreadsheet file (Excel) which provides simple and intuitive way to create a semantic data model. The spreadsheet obeys specific template, which represents the `Rules` object. The template is designed to be user friendly and to provide a simple way to define a semantic data model, offering a familiar environment for users who are not familiar with semantic data modeling.

To lower the entry barrier for the users, `Rules` are designed to be as simple as possible and profiled based on the role that a person has in the data modeling process. Consider consulting [the data modeling lifecycle tutorial](../tutorials/data-modeling-lifecycle/overview.md) for more detail on the process. The profiles are:

- Domain Expert
- Information Architect
- DMS CDF Architect

The amount of details that are requested from the user grows with the role that the user has in the data modeling process. Accordingly we will dive into the details of the `Rules` object per role in the following sections, which will be presented through the spreadsheet serialization of the `Rules` object.

`Rules` are composed of the following sheets, which based on the role (profile) are mandatory and/or optional or require various level of details:

- `Metadata`: contains metadata about the data model
- `Classes`: contains the high level definition of the classes that are part of the semantic data model (no properties)
- `Properties`: contains the definition of the properties per class
- `Views`: contains the definition of the CDF views that represent semantic data model serialization in CDF
- `Containers`: contains the definition of the CDF containers that are physical storage for data written/read in/from views
- `Prefixes`: contains the definition of the prefixes that are used in the semantic data model



## Metadata sheet

=== "Domain Expert Profile"


    | Field   | Description            | Predefined Value | Mandatory |
    |---------|------------------------|------------------|-----------|
    | role    | role of the person     | `domain expert`  | Yes       |
    | creator | names of data model creators separated with comma |              | Yes       |



=== "Information Architect Profile"

    | Field       | Description                                                      | Predefined Value                    | Mandatory |
    |-------------|------------------------------------------------------------------|-------------------------------------|-----------|
    | role        | the role of the person                                           | `domain expert`                     | Yes       |
    | creator     | names of data model creators separated with comma                |                                     | Yes       |
    | schema      | indication of schema completeness                                | `complete`, `partial` or `extended` | Yes       |
    | namespace   | data model namespace provided as URI                             |                                     | Yes       |
    | prefix      | data model prefix which is used as a short form of the namespace |                                     | Yes       |
    | version     | version of the data model                                        |                                     | Yes       |
    | created     | data model creation date                                         |                                     | Yes       |
    | updated     | data model last update date                                      |                                     | Yes       |
    | title       | title of the data model                                          |                                     | No        |
    | description | short description of the data model                              |                                     | No        |
    | license     | license of the data model                                        |                                     | No        |
    | rights      | usage right of the data model                                    |                                     | No        |


=== "DMS CDF Architect Profile"
    !!! warning annotate "Work in Progress"
        This section is a work in progress!


## Classes sheet

=== "Domain Expert Profile"
    Class sheet not mandatory for the domain expert profile, but if used should follow the Information Architect profile sheet.

=== "Information Architect Profile"

    | Column       | Description                                                    | Predefined Value     | Mandatory |
    |--------------|----------------------------------------------------------------|----------------------|-----------|
    | Class        | Class id being defined, use strongly advise `PascalCase` usage |                      | Yes       |
    | Name         | Human readable name of the class                               |                      | No        |
    | Description  | Short description of the class                                 |                      | Yes       |
    | Parent Class | Parent class id, used for property inheritance                 |                      | No        |
    | Reference    | Reference to the source of the class provided as `URI`         |                      | No        |
    | Match Type   | the match type between the source entity and the class         | `exact` or `partial` | No        |


=== "DMS CDF Architect Profile"
    !!! warning annotate "Work in Progress"
        This section is a work in progress!




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


=== "DMS CDF Architect Profile"
    !!! warning annotate "Work in Progress"
        This section is a work in progress!


## Prefixes sheet
The `Prefixes` sheet is only optional for the Information Architect profile. It must contain the following columns:

The `Prefixes` sheet only used for the Information Architect profile, and even in that it is optional.
If used it mus have the following columns:

- `Prefix`: the prefix that is used in the semantic data model
- `Namespace`: the namespace that the prefix represents provided as `URI`

## Views sheet
!!! warning annotate "Work in Progress"
    This section is a work in progress!


## Containers sheet
!!! warning annotate "Work in Progress"
    This section is a work in progress!
