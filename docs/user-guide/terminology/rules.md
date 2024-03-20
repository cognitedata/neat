# Rules
`Rules` is the core object in NEAT. This object is typically serialized as an Excel template which provides simple and intuitive way to create a semantic data model and knowledge graph. Multiple people can jointly collaborate and work on same data model since the template can be shared via SharePoint or as Google Sheets.


`Rules` in the Excel serialization contains following sheets:

- `Metadata`: contains metadata about the data model
- `Prefixes`: contains the definition of the prefixes that are used in the semantic data model and knowledge graph
- `Classes`: contains the definition of the classes that are part of the semantic data model as mapping of those classes to CDF resources such as Assets (classic CDF) or container/views (FDM)
- `Properties`: contains the definition of the properties that are part of the semantic data model, mapping of those properties to CDF resources and mapping of source data model and knowledge graph to the data model and knowledge graph that are being defined in the `Rules` (aka solution or target data model and knowledge graph)

Instead of explaining each sheet on its own we will explain how each part of the `Rules` is used to define:

- semantic data model
- semantic data model to CDF resource mapping
- source to solution data model and knowledge graph mapping

## Semantic Data Model Definition
First we start with the semantic data model definition. `Metadata` sheet contains metadata about data model. From the screenshot below one can see that the `Metadata` sheet is in a form of key value pairs. The `Key` column contains the name of the metadata attribute and the `Value` column contains the value of the metadata attribute. The metadata attributes are as follows:

- `prefix`: the data model prefix which is used as a short form of the namespace when data model is resolved as an RDF based data model, or it represents value for `space` when the model is resolved in CDF. This attribute is mandatory.
- `suffix`: used as represents an external id of data model, which will be used as DMS Data Model external id. This attribute is optional, if not provided NEAT will use `prefix` as the name of the data model.
- `namespace`: the data model namespace provided as URI. This attribute is optional, if not provided NEAT will automatically generate namespace based on the template `http://purl.org/cognite/{prefix}#`.
- `version`: version of the data model. This attribute is mandatory.
- `created`: data model creation date. This attribute is optional, defaults to date when Rules are loaded.
- `title`: title of the data model, when resolved as an RDF based data model, or as data model name when resolved in CDF. This attribute is optional, if not provided it will default to `suffix` attribute.
- `description`: short description of the data model. This attribute is optional but strongly advised.
- `creator`: creators of the data model separated by comma. This attribute is optional, defaults to `NEAT`.
- `contributor`: contributors to the data model separated by comma. This attribute is optional, defaults to `Cognite`.
- `rights`: usage right of the data model. This attribute is optional but strongly advised.
- `license`: license of the data model. This attribute is optional but strongly advised.


![Rules: Metadata Sheet](./artifacts/figs/metadata-sheet.png)


`Prefixes` sheet contains the definition of the prefixes that are used in the semantic data model and knowledge graph.

`Classes` sheet contains the definition of the classes that are part of the semantic data model. It is strongly advised to use `PascalCase` for the class names.

![Rules: Classes Sheet](./artifacts/figs/dm-classes.png)

!!! note annotate "Advance case - class id and class name are different"
    Column `Class` will be resolved as both class id and class name. In cases when class id and class name are different (e.g., cryptic class id), one can add additional column `Name`, and thus store both class id and class name. In such cases, `Class` column will be resolved as class id, and `Name` column will be resolved as class name.

`Properties` sheet contains the definition of the properties that are part of the semantic data model. This sheet contains more granular look on the semantic data model as properties are defined per each class including their cardinality and type of value they can hold. Therefore, in this sheet we are actually defining specific shape of classes.


Let's take a look at the screenshot below and define what each column means:

- `Class`: id of the class that the property belongs to (should be one of the values from `Class` column in `Classes` sheet). This attribute is mandatory. Class must be defined in the `Classes` sheet.
- `Property`: id (and name) of the property. This attribute is mandatory. It is strongly advised to use `camelCase` in this column.
- `Description`: short description of the property. This attribute is optional, but strongly advised.
- `Type`: type of the value that the property can hold. This attribute is mandatory. It takes either XSD type (simple types such as `string`, `float`, etc.) or a class defined in the `Classes` sheet (complex types).
- `Min Count`: minimum number of values that the property can hold. If no value is provided, the default value is `0`.
- `Max Count`: maximum number of values that the property can hold. If no value is provided, the default value is `inf`.

!!! note annotate "Advance case - property id and property name are different"
    Column `Property` will be resolved as both property id and property name. In cases when property id and property name are different (e.g., cryptic property id), one can add additional column `Name`, and thus store both class id and class name. In such cases, `Property` column will be resolved as property id, and `Name` column will be resolved as property name.


![Rules: Properties Sheet](./artifacts/figs/dm-object-shapes.png)

Combination of `Min Count` and `Max Count` attributes defines the shape of the property. The following table shows the possible combinations and their meaning:

| Min Count | Max Count | Meaning |
|-----------|-----------|---------|
| Not provided         | 1         | Optional single value property |
| Not provided         | None       | Optional multi value property |
| 1           | 1         | Mandatory single value property |
| 1           | Not provided       | Mandatory multi value property |


In the screenshot above we can see that we defined:

- `name` property for all classes as mandatory single value property that holds values of type `string`
- `TSO` property as mandatory multi value property that holds values of type `string`
- `priceArea` property as mandatory property which hold minimum two and maximum two values of type `PriceArea` (i.e., two references to instances of `PriceArea` class)

The definitions in the sheets above are converted by `NEAT` into [DMS Data Model](https://docs.cognite.com/cdf/data_modeling/). Optionally, the sheets can be converted to [RDF triples](https://www.oxfordsemantic.tech/fundamentals/what-is-a-triple). Specifically, `NEAT` produces [OWL](https://en.wikipedia.org/wiki/Web_Ontology_Language), which holds meaning of classes and properties, and [SHACL](https://en.wikipedia.org/wiki/SHACL) which holds structure of classes.

!!! note annotate "Knowledge Acquisition"
    In cases when model is previously been developed externally it is possible to store information about the original source of classes and properties. This can be done by adding additional columns `Source`, `Source Entity Name`,`Match Type` and `Comment` to `Classes` and `Properties` sheet. `Source` column should contain URI of the source of information, `Source Entity Name` contains the name of the entity in the source, `Match Type` contains the type of the match between the source entity and the class being described, and `Comment` contains additional information about the match.


## Semantic Data Model to CDF Resources Mapping
`Classes` and `Properties` sheets contain also columns that define how semantic data model instances (aka knowledge graph) are transformed/mapped to CDF resources. In the image below it is shown how data model is mapped to CDF `Assets` and `Relationships`.

![Rules: Properties Sheet](./artifacts/figs/dm2cdf-mapping.png)


This mapping is not needed when the data model is resolved for the Cognite Data Modeling service (i.e., DMS Data Model, Containers and Views).


## Source to Solution Data Model and Knowledge Graph Mapping
In typical scenario we would have knowledge graph, to which we would relate as `Source Graph` and we would perform transformations to `Solution Graph` which would be then mapped to CDF Resources. This mappings are defined in the `Properties` sheet of the `Rules` file, as one can see below:

![Rules: Properties Sheet](./artifacts/figs/dm-source-to-solution-mapping.png)

Various types of mappings are are defined in [Rule Type](./transformation-directive-types.md) section of this documentation. Make sure to check them out.
