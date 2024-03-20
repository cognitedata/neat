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


Now we will dwell into the details of the `Rules` object per role, thus per profile

## Domain expert profile
The most lightweight profile is the domain expert profile. The domain expert profile is designed for the domain expert who has deep knowledge about the domain that is being modeled. This person is typically not familiar with semantic data modeling and is not familiar with CDF. Therefore, the `Rules` object is designed to be as simple as possible and to require as little details as possible. The `Rules` object for the domain expert profile has two mandatory sheets, those being `Metadata` and `Properties`. The `Class` sheet is optional, but highly recommended.

### Metadata sheet
The `Metadata` must contain:

- `role`: the role of the person, which must be set to `domain expert`
- `creator`: the name of the person who is creating the `Rules` object, if multiple persons are creating the `Rules` object, the names are separated by comma

### Properties sheet
The `Properties` sheet must contain following columns, thus information per row:

- `Class`: id of the class that the property is defined for. This attribute is mandatory. It is strongly advised to use `PascalCase` in this column.
- `Property`: id of the property. This attribute is mandatory. It is strongly advised to use `camelCase` in this column.
- `Name`: human readable name of the property. This attribute is optional, but strongly advised if property id is cryptic.
- `Description`: short description of the property. This attribute is optional, but strongly advised.
- `Value Type`: type of the value that the property can hold. This attribute is mandatory. It takes either subset of XSD type (see note below) or a class defined in the `Classes` sheet
- `Min Count`: minimum number of values that the property can hold. If no value is provided, the default value is `0`.
- `Max Count`: maximum number of values that the property can hold. If no value is provided, the default value is `inf`.

<a id="xsd-type-anchor"></a>
!!! info annotate "XSD Value Types"
    The following XSD types are supported:
    `boolean`, `float`, `double` ,`integer` ,`nonPositiveInteger` ,`nonNegativeInteger` ,`negativeInteger` ,`long` ,`string` ,`langString` ,`anyURI` ,`normalizedString` ,`token` ,`dateTime` ,`dateTimeStamp`  and `date`.
    In addition to the subset of XSD types, the following value types are supported:
    `timeseries`, `file` , `sequence` and `json`


### Classes sheet
The `Class` sheet, which is optional, if to be used must contain following columns, thus information per row:

- `Class`: id of the class. This attribute is mandatory. It is strongly advised to use `PascalCase` in this column.
- `Name`: human readable name of the class. This attribute is optional, but strongly advised if class id is crypt
- `Description`: short description of the class. This attribute is optional, but strongly advised.
- `Parent Class`: id of the parent class, which is used for inheritance. This attribute is optional, if not provided the class is considered to be a top level class.



## Information Architect profile
The information architect profile is designed for the person who is familiar with semantic data modeling. This person is typically responsible for creating the semantic data model and the knowledge graph. The `Rules` object for the information architect profile has three mandatory sheets, those being `Metadata`, `Classes` and `Properties`, and optional `Prefixes` sheet if there are any prefixes used beyond the core prefix being defined with the data model.

### Metadata sheet
The `Metadata` must contain, everything that is mandatory for the domain expert profile, plus:

- `role`: the role of the person, which must be set to `information architect`
- `namespace`: the data model namespace provided as URI. This attribute is mandatory.
- `prefix` : the data model prefix which is used as a short form of the namespace when data model is resolved as an RDF based data model. This attribute is mandatory.
- `version`: version of the data model. This attribute is mandatory.
- `schema`: a indication of schema completeness, which can be either one of the following:
    - `complete`: the data model is entirely defined in the spreadsheets
    - `partial`: the data model is defined within several spreadsheets
    - `extended`: data model is defined in spreadsheets and external sources (ontology, CDF, etc.)
- `title`: title of the data model, when resolved as an RDF based data model. This attribute is optional, but strongly advised.
- `description`: short description of the data model. This attribute is optional, but strongly advised.
- `created`: data model creation date. This attribute is mandatory.
- `updated`: data model last update date. This attribute is mandatory.
- `license`: license of the data model. This attribute is optional but strongly advised.
- `rights`: usage right of the data model. This attribute is optional but strongly advised.

### Classes and Properties sheet
The `Classes` and `Properties` sheets must contain the same columns as for the domain expert profile, and can have in addition optional columns:

- `Reference`: reference to the source of the class or property provided as `URI`
- `Match Type`: type of the match between the source entity and the class or property

If the `Rules` object is used also to populate data model using [NEAT graph store](./graph.md), there are additional columns that are mandatory for the `Properties` sheet:

- `Rule Type`: type of the rule that is used to populate the data model, which can take one of the following values:
    - `sparql`: SPARQL query that resolves against [NEAT graph store](./graph.md)
    - `rdfpath`: simplified graph query directive that resolves as SPARQL query against [NEAT graph store](./graph.md)
    - `rawlookup`: resolves as combination of `sparql` query against [NEAT graph store](./graph.md) and query against CDF RAW
- `Rule`: the rule that is used to populate the data model. The rule is provided as a string, which is either SPARQL query or RDFPath query or RAW lookup query.

The range of value types is the same like in case of the domain expert profile (see more  [here](#xsd-type-anchor)).

### Prefixes sheet
The `Prefixes` sheet, if provided must contain the following columns:

- `Prefix`: the prefix that is used in the semantic data model
- `Namespace`: the namespace that the prefix represents provided as `URI`

## DMS CDF Architect
!!! warning annotate "Work in Progress"
    This section is a work in progress!
