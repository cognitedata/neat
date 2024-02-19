# Data Modeling Lifecycle through Expert Elicitation: Building an Enterprise Data Model

!!! note annotate "Warning"
    This tutorial is a work in progress and is not yet complete.

This tutorial demonstrates the usage of `neat` through out the entire data modeling lifecycle producing an Enterprise Data Model in Cognite Data Fusion (CDF).
The data modeling lifecycle is based on the so-called [Expert Elicitation](https://en.wikipedia.org/wiki/Expert_elicitation), and represents the recommended way of building enterprise data models.


## Introduction

Companies typically have multiple domain experts that working in different business units. Typically, these
units are partially overlapping, both in concepts and data. Lots of the value in a product like CDF comes from
taking data from different sources and making them easily accessible and understandable for all domain experts and all business units, as
this unlocks the potential for cross-domain insights.

The expert elicitation is the process of taking the knowledge from domain experts and turning it into a shared knowledge artifact such as an Enterprise Data Model (covering the entire suite of use-cases and domains and business units).
`neat` has been designed to facilitate this process by providing a way to iterate on and developed this model.

## Use Case

In this tutorial, we will focus on the Power & Utilities industry. We will have two domain experts, one that
focuses on wind farm operation and one that focuses on grid analysis, lets call them Jon and Emma. In addition,
we will have an information architect, let's call him David, who will be responsible for combining the
knowledge from Jon and Emma into an enterprise data model. Finally, we have a CDF expert, let's call her Alice,
who will be responsible for implementing the enterprise data model in CDF. Note that in a real-world scenario,
the information architect and the CDF solution architect (DMS - domain model service architect) might be the same
person, but for the purpose of this tutorial, we will keep them separate to highlight that their required skills
and how they use `neat` are different.

**Note** You don't need to be an expert in the Power & Utilities industry to follow this tutorial. The concepts
are generic and can be applied to any industry in which you have domain experts with overlapping knowledge and data.
We have purposely simplified the domains to make it easier to follow this tutorial.

## Wind Farm Operation Expert: Jon

### Gathering Knowledge
In `neat`, knowledge is captured in statements (i.e. sentences). A statement is a simple fact about a thing (e.g. wind turbine). In this tutorial, we will collect statements that describe the properties of physical objects that constitute an operational wind farm connected to a transmission grid. We will start with a wind turbine.

For example, Jon might say that a wind turbine has a `name`, a `location`, `manufacturer`, `ratedPower`, `hubHeight`, `actualPower` and `arrayCableConnection`. These are all
statements. In `neat`, we capture these statements in a spreadsheet format. We refer to a set of
statements as `Properties`. The `Properties` sheet looks as follows for a domain expert like Jon:

| Class       | Property           | Description     | Value Type  | Min Count  | Max Count  |
|-------------|--------------------|-----------------|-------------|------------|------------|
| WindTurbine | name               |                 | string      | 1          | 1          |
| WindTurbine | location           |                 | string      | 0          | 1          |
| WindTurbine | manufacturer       |                 | string      | 0          | 1          |
| WindTurbine | lifeExpectancy     |                 | integer     | 1          | 1          |
| WindTurbine | ratedPower         |                 | float       | 1          | 1          |
| WindTurbine | hubHeight          |                 | float       | 1          | 1          |
| WindTurbine | actualPower        |                 | timeseries  | 1          | 1          |
| WindTurbine | arrayCableConnection |               | integer     | 1          | 1          |
| WindFarm    | name               |                 | string      | 1          | 1          |
| WindFarm    | location           |                 | string      | 0          | 1          |
| WindFarm    | windTurbine        |                 | WindTurbine | 1          | Inf        |
| Substation  | inputVoltage       |                 | timeseries  | 1          | 1          |
| Substation  | outputVoltage      |                 | timeseries  | 1          | 1          |
| ExportCable | voltageLevel       |                 | float       | 1          | 1          |
| ExportCable | currentVoltage     |                 | timeseries  | 1          | 1          |

In each row of the `Properties` sheet, Jon will define a statement. For example, the first row says that a
`WindTurbine` has a `name`. In addition, Jon can add a `description`, i.e., a human-readable explanation of what a particular property means. The three next columns help the information architect, David, to understand how to model the data. First, we have the
`Value Type` column, which specify what type of data this statement is about. Is this a number, an on/off value, text,
or something else? In this case, the `name`, `location`, and `manufacturer` are all strings, meaning they are
expected to be text. The `Min Count` and `Max Count` columns specify how many data points are expected for each of these properties. In the
first row, we see that a `WindTurbine` is expected to have exactly one `name`. Sames goes for the `location` and `manufacturer`. However, for `lifeExpectancy`, we see that it is optional, as the `Min Count` is 0. Also, `lifeExpectancy` is an integer, as it is expected to be a whole number.


In the similar fashion, Jon defines the properties for `WindFarm`, `Substation` and `ExportCable` in the `Properties` sheet.

In addition to the `Properties` sheets, `neat` also requires one more sheet `Metadata` for domain experts.
In case of domain expert the `Metadata` sheet only requires `role` and `creator` to be set, where `role` represent the role a person has in modeling of the enterprise data model and `creator` is the name of the person from whom we are acquiring knowledge to create the model.
For Jon the `Metadata` sheet looks as follows:

|         |               |
|---------|---------------|
| role    | domain expert |
| creator | Jon           |


Optionally, domain experts can also define classes in the `classes` sheet. Classes are used to group properties that define a thing. For example, a `WindTurbine` is a class, and the set of properties for a class defines what it means to be a member of that class. However, as it is optional, Jon skips this sheet, and leaves it to the information architect, David, to define that for him.

Download Jon's spreadsheet from [here](spreadsheets/expert-wind-energy-jon.xlsx).


### Validating Statements in Neat
When Jon has defined all the statements, he can validate the sheet using `neat`. This will check that all the
statements are correctly defined and that there are no inconsistencies. For example, that all properties
are using valid characters in their names.

To validate his sheet, Jon opens the `neat` UI and selects the `Validate Rules` workflow:

<img src="images/validate_workflow.png" height="300">

Then, his sheet is named `jon_wind_turbine.xlsx`, and he needs to go into the `Validate Rules` step and
change the configuration to point to his sheet:

<img src="images/change_validate_step.png" height="300">

Finally, he can click the `RunWorkflow` button to validate his sheet and it will outut a report with any errors
and warnings.

<img src="images/run_workflow.png" height="300">

### Summary

**Domain Expert Task.**

1. (Required) Gathering statements in a spreadsheet.
2. (Optional) Defining classes in a spreadsheet.

**Domain Expert usage of `neat`**:

1. Validate the sheet using the `neat` UI.


## Grid Analysis Expert: Emma

### Gathering Knowledge
Similarly to Jon, Emma will define a set of statements in a spreadsheet. As being more meticulous and keen to go one step further she will also fill in `Classes` sheet. Like in case of Jon, she starts with `Properties` sheet. She defines some similar statements as Jon, but also adds completely new ones. This is expected as there are overlaps between in our case the power production and power transmission domains.

For example, she defines
`Substation` has a `name`, a `location`, and a `voltage`. In addition, she might define that a `Substation` has
a `transformer` and a `circuit breaker`, and she has also adds a `GeneratingUnit` that has a `name` and `activePower`.
The `Properties` sheet for Emma might look as follows:

| Class         | Property                 | Description | Value Type           | Min Count | Max Count |
|---------------|--------------------------| ----------- |----------------------|-----------|-----------|
| GeneratingUnit| name                     |             | string               | 1         | 1         |
| GeneratingUnit| type                     |             | string               | 1         | 1         |
| GeneratingUnit| activePower              |             | float                | 1         | 1         |
| Substation    | name                     |             | string               | 1         | 1         |
| Substation    | location                 |             | string               | 0         | 1         |
| Substation    | disconnectSwitch         |             | DisconnectSwitch     | 2         | 2         |
| Substation    | circuitBreaker           |             | CircuitBreaker       | 2         | 2         |
| Substation    | currentTransformer       |             | CurrentTransformer   | 2         | 2         |
| Substation    | mainTransformer          |             | VoltageTransformer   | 1         | 1         |
| Transmission  | name                     |             | string               | 1         | 1         |
| Transmission  | location                 |             | string               | 0         | 1         |
| Transmission  | voltage                  |             | number               | 1         | 1         |
| Transmission  | substation               |             | Substation           | 1         | 1         |
| Distribution  | name                     |             | string               | 1         | 1         |
| Distribution  | location                 |             | string               | 0         | 1         |
| Distribution  | voltage                  |             | number               | 1         | 1         |
| Distribution  | substation               |             | Substation           | 1         | 1         |
| Consumer      | name                     |             | string               | 1         | 1         |
| Consumer      | location                 |             | string               | 0         | 1         |
| Consumer      | load                     |             | number               | 1         | 1         |
| Consumer      | type                     |             | string               | 1         | 1         |





As mentioned earlier, Emma also abstracts classes from `Properties` sheet and puts them in `Classes` sheet to have a better overview of her domain, de-cluttered from properties. To differentiate between `CurrentTransformer` and `VoltageTransformer` she also adds a `Parent Class` column to the `Classes` sheet, indicating that these two classes are indeed a specialization of `Transformer`. The `Classes` sheet for Emma might look as follows:


| Class              | Description                                         | Parent Class       |
|--------------------|-----------------------------------------------------|--------------------|
| Substation         | A part of an electrical grid                        |                    |
| Transformer        | A device that changes electrical voltage or current |                    |
| CurrentTransformer | A device that changes electrical voltage or current | Transformer        |
| VoltageTransformer | A device that changes electrical voltage or current | Transformer        |
| CircuitBreaker     | A device that can stop the flow of electricity      |                    |
| DisconnectSwitch   | A device that can stop the flow of electricity      |                    |
| GeneratingUnit     | A device that generates electrical energy           |                    |
| Transmission       | A part of an electrical grid                        |                    |
| Distribution       | A part of an electrical grid                        |                    |
| Consumer           | A part of an electrical grid                        |                    |


Like in the case of Jon, Emma also fills in the `Metadata` sheet. For Emma the `Metadata` sheet looks as follows:

|         |               |
|---------|---------------|
| role    | domain expert |
| creator | Emma          |


You can find the complete `Properties`, `classes`, and `metadata` sheets for Emma here.

Finally, Emma will validate her sheet using the `neat` UI, just like Jon did.

Download Emma's spreadsheet from [here](spreadsheets/expert-grid-emma.xlsx).

### Summary

**Domain Expert Task.**

1. (Required) Gathering statements in a spreadsheet.
2. (Optional) Defining classes in a spreadsheet.

**Domain Expert usage of `neat`**:

1. Validate the sheet using the `neat` UI.


## Information Architect: David

### Creating the Shared Data Model

Once Jon and Emma have defined their statements, David will combine the two sheets into a single sheet. This is
done by copying the statements from Jon and Emma into a single sheet and making a tough decision on how to combine them to produce the enterprise data model. For example, if Jon and Emma have defined the same property in different ways, David will have to decide which definition to use. In certain situations additional classes and properties will have to be added to connect two domains. This is a trade-off, as he might have to prompt Jon and Emma for clarification, or he might have to make a decision based on his own knowledge.


Let start with `Classes` sheet and investigate outcome of merging Jon's and Emma's classes:

| Class                  | Description | Parent Class   | Source                                               | Match   |
|------------------------|-------------|----------------|------------------------------------------------------|---------|
| GeneratingUnit         |             |                | http://www.iec.ch/TC57/CIM#GeneratingUnit            | exact   |
| WindTurbine            |             | GeneratingUnit | http://purl.org/neat/WindTurbine                     | exact   |
| EnergyArea             |             |                | http://www.iec.ch/TC57/CIM#EnergyArea                |         |
| WindFarm               |             | EnergyArea     | http://purl.org/neat/WindFarm                        | partial |
| Substation             |             |                |                                                      |         |
| OffshoreSubstation     |             | Substation     |                                                      |         |
| TransmissionSubstation |             | Substation     |                                                      |         |
| DistributionSubstation |             | Substation     |                                                      |         |
| PowerLine              |             |                |                                                      |         |
| ArrayCable             |             | PowerLine      |                                                      |         |
| ExportCable            |             | PowerLine      |                                                      |         |
| Transmission           |             | PowerLine      |                                                      |         |
| EnergyConsumer         |             |                | http://www.iec.ch/TC57/CIM#EnergyConsumer            |         |
| Factory                |             | EnergyConsumer |                                                      |         |
| GeoLocation            |             |                | http://www.w3.org/2003/01/geo/wgs84_pos#SpatialThing |         |
| Point                  |             | GeoLocation    | https://purl.org/geojson/vocab#Point                 |         |
| MultiLineString        |             | GeoLocation    | https://purl.org/geojson/vocab#MultiLineString       |         |
| Polygon                |             | GeoLocation    | https://purl.org/geojson/vocab#Polygon               |         |


There are couple of things that David done. First of all, he use principle of subclassing to create a class specialization in order to satisfy both Jon's and Emma's definitions. For example, he created a `WindTurbine` class that is a subclass of `GeneratingUnit`. This is done by adding a `Parent Class` column to the `Classes` sheet. By doing this, he enable adding additional types of generating units in the future. In the same fashion, he also created a `WindFarm` class that is a subclass of `EnergyArea`, basically connecting the two domains and allowing for other types of energy areas to be defined in the future. We see the similar approach with `Substation`, `Transmission`, `EnergyConsumer`, and `Point`. on`. By sub-classing we enable the possibility to inherit properties from the parent class, avoiding the need to define the same properties for each subclass, which we will see in the `Properties` sheet.

In addition, David also added a `Source` and `Match` columns to the `Classes` sheet. The `Source` column is used to specify where the statement comes from, or what standard that matches the statement. The `Match` column tells whether the source is partially or fully matching the statement. We see that David did a great work linking the enterprise data model to existing standards, such as the CIM standard for energy areas and energy consumers. This is a good practice, as it sets the knowledge into a broader context, allowing for easier integration with other systems and standards. In other words, David did not fall into a trap of reinventing the wheel, but rather leveraged existing standards to define the enterprise data model (what a smart guy!).


Let's now move to the `Properties` sheet. David will also combined and uplifted the `Properties` sheets from Jon and Emma:


| Class              | Property             | Description | Value Type         | Min Count | Max Count | Default | Source                                           |
|--------------------|----------------------|-------------|--------------------|-----------|-----------|---------|--------------------------------------------------|
| GeneratingUnit     | name                 |             | string             |         1 |         1 |         |                                                  |
| GeneratingUnit     | type                 |             | string             |         1 |         1 |         |                                                  |
| GeneratingUnit     | activePower          |             | timeseries         |         1 |         1 |         |                                                  |
| GeneratingUnit     | geoLocation          |             | Point              |         1 |         1 |         | http://www.w3.org/2003/01/geo/wgs84_pos#location |
| WindTurbine        | manufacturer         |             | string             |         0 |         1 |         |                                                  |
| WindTurbine        | ratedPower           |             | float              |         1 |         1 |         |                                                  |
| WindTurbine        | hubHeight            |             | float              |         1 |         1 |         |                                                  |
| WindTurbine        | arrayCableConnection |             | ArrayCable         |         1 |         1 |         |                                                  |
| WindTurbine        | lifeExpectancy       |             | integer            |         0 |         1 |         |                                                  |
| PowerLine          | voltageLevel         |             | VoltageLevel       |         1 |         1 |         |                                                  |
| PowerLine          | geoLocation          |             | MultiLineString    |         1 |         1 |         |                                                  |
| PowerLine          | currentVoltage       |             | timeseries         |         1 |         1 |         |                                                  |
| Substation         | name                 |             | string             |         1 |         1 |         |                                                  |
| Substation         | location             |             | string             |         0 |         1 |         |                                                  |
| Substation         | disconnectSwitch     |             | DisconnectSwitch   |         2 |         2 |         |                                                  |
| Substation         | circuitBreaker       |             | CircuitBreaker     |         2 |         2 |         |                                                  |
| Substation         | currentTransformer   |             | CurrentTransformer |         2 |         2 |         |                                                  |
| Substation         | mainTransformer      |             | VoltageTransformer |         1 |         1 |         |                                                  |
| Substation         | primaryPowerLine     |             | PowerLine          |         1 |         1 |         |                                                  |
| Substation         | secondaryPowerLine   |             | PowerLine          |         1 |         1 |         |                                                  |
| Substation         | primaryVoltage       |             | timeseries         |         1 |         1 |         |                                                  |
| Substation         | secondaryVoltage     |             | timeseries         |         1 |         1 |         |                                                  |
| OffshoreSubstation | primaryPowerLine     |             | ArrayCable         |         1 | inf       |         |                                                  |
| OffshoreSubstation | secondaryPowerLine   |             | ExportCable        |         1 |         1 |         |                                                  |
| EnergyArea         | name                 |             | string             |         1 |         1 |         |                                                  |
| EnergyArea         | geoLocation          |             | Polygon            |         0 |         1 |         |                                                  |
| EnergyArea         | ratedPower           |             | float              |         1 |         1 |         |                                                  |
| EnergyArea         | activePower          |             | timeseries         |         1 |         1 |         |                                                  |
| WindFarm           | windTurbine          |             | WindTurbine        |         1 | Inf       |         |                                                  |
| WindFarm           | substation           |             | OffshoreSubstation |         1 |         1 |         |                                                  |
| WindFarm           | arrayCable           |             | ArrayCable         |         1 | inf       |         |                                                  |
| WindFarm           | exportCable          |             | ExportCable        |         1 |         1 |         |                                                  |
| Factory            | name                 |             | string             |         1 |         1 |         |                                                  |
| Factory            | location             |             | Point              |         1 |         1 |         |                                                  |
| Factory            | load                 |             | timeseries         |         1 |         1 |         |                                                  |
| Point              | latitude             |             | float              |         1 |         1 |         |                                                  |
| Point              | longitude            |             | float              |         1 |         1 |         |                                                  |
| MultiLineString    | point                |             | Point              |         2 |       inf |         |                                                  |
| Polygon            | point                |             | Point              |         3 |       inf |         |                                                  |



Here we see how inheritance and proper modeling of classes pays off. Instead of repeating properties from `GeneratingUnit` for `WindTurbine`, David only needs to define the properties specific only `WindTurbine`. This is because `WindTurbine` is a subclass of `GeneratingUnit`, and thus inherits all the properties from `GeneratingUnit`. This is a good practice, as it reduces the amount of work needed to define the enterprise data model. In addition, it also makes the enterprise data model more consistent, as the same properties are used for similar things. Let's now have a look at statements for `OffshoreSubstation`, in `Classes` sheet David stated that `OffshoreSubstation` is a subclass of `Substation`, and in `Properties` sheet he only needs specialized type of values two properties take in order to make this class a specific subclass of `Substation`. This is a good example of how inheritance can be used to reduce the amount of work needed to define the enterprise data model. Similar like in the case of `Classes` sheet David also added a `Source` and `Match` columns to link the enterprise data model to existing standards, in this case to definition of properties coming from different standards.
In addition, David will needs to update a `metadata` sheet, he is adding :

- `namespace` : to define a unique identifier for the enterprise data model globally
- `prefix` : to define a short name that can be used to reference the namespace in various downstream systems
- `create` : to define the date when the enterprise data model was created
- `updated` : to define the date when the enterprise data model was last updated
- `version` : to define the version of the enterprise data model
- `title` : to define the title of the enterprise data model
- `description` : to define the description, giving it a human-readable explanation of what the enterprise data model is about
- `license` : to define the license of the enterprise data model, basically in what way it can be used
- `rights` : to define the rights of the enterprise data model, basically who has the right to use it

He is adding him self as a contributor, while presenting Jon and Emma as creators. The `metadata` sheet for David might look as follows:

|             |                                        |
|-------------|----------------------------------------|
| role        | information architect                  |
| creator     | David, Emma                            |
| contributor | David                                  |
| namespace   | http://purl.org/cognite/power2consumer |
| prefix      | power                                  |
| created     | 2024-01-22                             |
| updated     | 2024-02-09                             |
| version     | 0.1.0                                  |
| title       | Power to Consumer Data Model           |
| description | end2end power to consumer data model...|
| license     | CC-BY 4.0                              |
| rights      | Free for use                           |


The enterprise data model is now ready to be validated in `neat`. David will validate his sheet using the `neat` UI, just like Jon and Emma did. However, since David has set his role as `information architect` in the `metadata` sheet, the validation from `neat` will be more strict. For example, while Jon and Emma can skip defining anything in the `class` sheet, David will have to ensure all classes are defined. Also, there is more demand when comes to `metadata`.

Nevertheless, this hard work pays off since the enterprise data model can be now used to digitally represent the entire power to consumer domain in the form of rich knowledge graph empowering services from various domains.

<!-- TODO:
- Explain a bit more about disconnect in classes from wind expert
- Why we switch from string to actual object to represent location
- Why we used CIM, GeoJSON, and WGS84 standards to define the enterprise data model
- ... -->

### Iterating over the Sheet

Looking over the `Properties` sheet, David notice that `WindGenerator` from Emma and `WindTurbine` from Jon are
very similar. He decides to prompt Emma and Jon for clarification. After a short discussion, they decide that
`WindGenerator` and `WindTurbine` are the same thing, and they decide to use `WindTurbine` as the class name.

An alternative approach would be that keep both classes, but add a property to the `WindGenerator` class that
specifies that it is a type of `WindTurbine`. This would be done by using the `Parent Class` column in the
`classes` sheet.

| Class           | Description                                         | Parent Class   |
|-----------------|-----------------------------------------------------|----------------|
| WindTurbine     | A device that converts wind to electrical energy    | WindGenerator  |


### Extending the Sheet

David will also add two new columns to the `Properties` sheet. The first column is called `Source`, and it is used
to specify where the statement comes from, or what standard that matches the statement. The second column is called
`MatchType`, and tells whether the source is partially or fully matching the statement.

| Class         | Property         | Description | Type           | Min Count | Max Count | Source                               | MatchType |
|---------------|------------------| ----------- |----------------|-----------|-----------|--------------------------------------|-----------|
| WindTurbine   | name             |             | string         | 1         | 1         | http://purl.org/windstandard/turbile | full      |

This way David can link the statements up to an existing standard, which sets the knowledge into a broader context.

### Validating in Neat
Like Jon and Emma, David will validate his sheet using the `neat` UI, using the same workflow `Validate Rules`.
Note that since David has set his role as `information architect` in the `metadata` sheet, the validation
from `neat` will be more strict. For example, while Jon and Emma can skip defining anything in the `class` sheet,
David will have to ensure all classes are defined.

The advantage of the additional validation is that it can now unlock additional features in `neat`, such as
visualization and exporting to OWL.

### Exporting to OWL

Once David has validated his sheet, he can export it to OWL. This is done by using the `Export OWL` workflow in
the `neat` UI. This will generate an OWL file that can be used in any ontology tool, such as Protege.

TODO Step by step guide on how to export to OWL.

### Visualization in Neat

Another useful feature of `neat` is that it can visualize the shared data model. This is done by using the
`Visualize` workflow in the `neat` UI. This will generate a graph that shows the classes and properties and how
they are connected.

TODO Step by step guide on how to visualize the shared data model.

### Summary

**Information Architect Task.**

1. Add statements that connect concepts from different domain experts.
2. Add metadata to the sheet.
3. Add source column to the `Properties` sheet.
4. Add MatchType column to the `Properties` sheet.
5. Find overlapping concepts and prompt domain experts for clarification.
6. Add all classes to the `classes` sheet.

**Information Architect usage of `neat`**:

1. Validate the sheet using the `neat` UI.
2. Visualize the sheet using the `neat` UI.
3. Export the ontology to an open standard format (e.g., OWL, RDF, JSON-LD).


## DMS Architect: Alice

### Implementing the Enterprise Data Model in CDF
Neat supports exporting a data model to CDF either using an `AssetLoader` or `DMSLoader`. The `AssetLoader` is
used to load the data model into the classical `AssetHierarchy` in CDF, while the `DMSLoader` is used to load the
data model into the new Data Modeling Service (DMS) in CDF. The `DMSLoader` is the recommended way to load the
data model into CDF, as it supports more advanced features such as defining dependencies between data. In this
tutorial, we will focus on the `DMSLoader`.

Once David has defined the enterprise data model, Alice will implement it in CDF. The focus of Alice is to make sure
that the enterprise data model is implemented in CDF in a way that accounts for the expected usage of the data. For example, she
needs to define how the data is stored and what properties are indexed for fast queries. In addition, she decides
which dependencies between data should be enforced. This is a trade-off in that being very strict on the data
makes it easy to use as it is predictable. However, it can be hard to populate it as large quantities of the
data might not be in the expected format. On the other hand, being very flexible on the data puts a higher burden
on the developers/users that use the data.

Her tasks can be divided into **performance** and **quality** and summarized as follows:

1. **Performance**:
   - Which indexes to create?
   - The size of the containers.
   - Implement relationships as edges or direct relations.
2. **Quality**:
   - Define constraints between containers
   - Define constraints between properties
   - Define uniqueness constraints on properties
   - Decide which properties should be mandatory.
   - Decide value types for properties (for example int32 vs int64).

### Extending the <code>metadata</code> Sheet

Alice has to modify the `metadata` sheet to include the CDF specific information.

|             |                         |
|-------------|-------------------------|
| role        | dms architect           |
| prefix      | power                   |
| namespace   | pwr                     |
| space       | sp_power                |
| externalId  | power_enterprise_model  |
| version     | 1                       |
| contributor | Jon, Emma, David, Alice |
| created     | 2021-01-01              |
| updated     | 2021-01-01              |

First, she adds herself as a contributor, and then she adds the `space` and `externalId` columns. The `space`
column is used to define the space in CDF where the data model should be loaded. The `externalId` column is used
to define the external id of the enterprise data model. This is used to reference the data model from other parts of CDF.

### The <code>properties</code> Sheet

Using the workflow `To DMS Rules`, Alice will convert the `properties` sheet to a DMS format. This will add
nine new columns as well as modify the `Value Type` column. The first row of the `properties` sheet for Alice
might look as follows:

| Class         | Property         | ValueType | Relation | Nullable | IsList | Container  | Container Property | Index | Constraints | View        | View Property |
|---------------|------------------|-----------|----------|----------|--------|------------|--------------------|-------|-------------|-------------|---------------|
| WindTurbine   | name             | Text      |          | False    | False  | PowerAsset | name               | name  |             | WindTurbine | name          |

`neat` will fill out all the new columns with suggested values, but Alice can modify them as she sees fit and thus
she has granular control over how the data should be stored in CDF.

The columns are as follows:

#### How to store the properties in CDF

* **Value Type**: The values in the Value Type columns are converted to the types supported by DMS. For example, the
  `string` type is converted to `Text`. Alice must still check and potentially modify the value types to ensure
  that they are correct. For example, `float` are converted to `float64`, and Alice might decide to change it to
  `float32` if she knows that the values will never be larger than 32 bits.
* **Relation**: This columns only applies to relationships between entities. It is used to specify how the relationship
  should be implemented in CDF. For example, if the relationship should be implemented as an edge or as a direct
    relation.
* **Nullable**: This only applies to primitive types. This column is used to specify whether the property is
  required or not. For example, Alice might decide that the `name` property of a `WindTurbine` is required,
  and she will set the `Nullable` column to `False`.
* **IsList**: This only applies to primitive types. This column is used to specify whether the property is a list or not.

#### Where to store the properties in CDF

* **Container**: This column is used to specify which container the data should be stored in. For example, Alice might
  decide that the `WindTurbine` data should be stored in a container called `PowerAsset`.
* **Container Property**: This column is used to specify which property in the container that the data should be
  stored in. For example, Alice might decide that the `WindTurbine` data should be stored in a property called `name`
  in the `PowerAsset` container.
* **Index**: This column is used to specify whether the property should be part of an index. For example, Alice might
  decide that the `name` property of a `WindTurbine` should be part of an index, and she will set the `Index` column
  to `name`.
* **Constraints**: This column is used to specify constraints. For exmaple, Alice might decide that the `name`
  property of a `WindTurbine` should be unique, so she will set the `Constraints` column to `unique`. If the property
  is a relation implemented as a direct relation, Alice can also specify that the source (other end of the relation)
  should be in a specific container.

#### How to consume the properties in CDF
* **View**: This column is used to specify which view the property should be part of. For example, Alice might decide
  that the `name` property of a `WindTurbine` should be part of a view called `WindTurbine`.
* **View Property**: This column is used to specify what the property should be called in the view.

### The <code>Container</code> Sheet

The output of the `To DMS Rules` will produce two new sheets `Container` and `View`. The `Container` sheet is used
to define constraints between the containers. The first three rows of the `Container` sheet for Alice look
as follows:

| Container      | Description | Constraint     |
|----------------|-------------|----------------|
| PowerAsset     |             |                |
| GeneratingUnit |             | PowerAsset     |
| WindTurbine    |             | GeneratingUnit |


Interpreting the first three rows, we see that all entries in the `GeneratingUnit` container must have a corresponding
entry in the `PowerAsset` container. In addition, all entries in the `WindTurbine` container must have a corresponding
entry in the `GeneratingUnit` container (and thus also the `PowerAsset` container.

### The <code>View</code> Sheet

The `View` sheet is used to define which views implements other views. Implements means that a view is reusing the
properties from another view. The first three rows of the `View` sheet for Alice look as follows:


| View           | Description | Implements     |
|----------------|-------------|----------------|
| PowerAsset     |             |                |
| GeneratingUnit |             | PowerAsset     |
| WindTurbine    |             | GeneratingUnit |


Interpreting the first three rows, we see that the `GeneratingUnit` view is reusing the properties from the `PowerAsset`
view, and the `WindTurbine` view is reusing the properties from the `GeneratingUnit` view. It is the hierarchy of views
will overlap the constraints between the containers, as Alice have chosen for this case. However, it is important
to note that the `View` and `Container` sheets are describing different things. The `Container` sheet is used to
define constraints between the containers, Alice could have chosen to have no constraints between the `GeneratingUnit`
and `WindTurbine` containers, but she still kept reusing the properties from the `PowerAsset` view. Similarly, Alice
could have kept the constraints, and rewritten all properties for the `WindTurbine` view, without reusing the properties
from the `GeneratingUnit` and `PowerAsset` views.

Download Alice's spreadsheet from [here](spreadsheets/cdf-dms-architect-alice.xlsx).

### Validating in Neat

Like Jon, Emma, and David, Alice will validate her sheet using the `neat` UI, using the same workflow `Validate Rules`.
Note that since Alice has set her role as `dms architect` in the `metadata` sheet, the validation from `neat` will be
suited for the DMSExported. Meaning that it will check that the rules can exported to CDF in a DMS format.


### Exporting DMS to YAML

Once Alice has validated her sheet, she can export it to YAML. This is done by using the `Export DMS` workflow in
the `neat` UI. This will generate a YAML file that can be used to load the data model into CDF.

This is useful if she want to give the data model to `cognite-toolkit` which can then govern the data model in CDF.

TODO Step by step guide on how to export to YAML.

### Exporting DMS to CDF

Once Alice has validated her sheet, she can export it to CDF. This is done by using the `Export DMS to CDF` workflow in
the `neat` UI. This will load the data model into CDF.

TODO Step by step guide on how to export to CDF.

### Summary

**DMS Architect Task.**

1. Add metadata about CDF to `metadata` sheet.
2. Add columns to `Properties` sheet for how the data should be stored in Data Modeling containers.
3. Select which properties should be indexed for fast search.
4. Define dependencies between data by defining Data Modeling views.

**DMS Architect usage of `neat`**:

1. Validate the sheet using the `neat` UI.
2. Export DMS schema to `YAML`.
3. Export DMS schema to `CDF`.
