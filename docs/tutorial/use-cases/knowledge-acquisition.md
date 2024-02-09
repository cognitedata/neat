# Knowledge Acquisition

!!! note annotate "Warning"
    This tutorial is a work in progress and is not yet complete.

This tutorial covers how to use `neat` for knowledge acquisition and produce a shared data model in
Cognite Data Fusion (CDF). The process of knowledge acquisition follows the so-called
[Expert Elicitation](https://en.wikipedia.org/wiki/Expert_elicitation), and represents the recommended way of
building enterprise data models.

## Introduction

Companies typically have multiple domain experts that cover different areas of the business. Typically, these
areas are partially overlapping, both in concepts and data. Lots of the value in a product like CDF comes from
taking data from different sources and making it easily accessible and understandable for all domain experts (i.e., making data to talk domain expert language), as
this unlocks the potential for cross-domain insights.

Knowledge acquisition is the process of taking the knowledge from domain experts and turning it into a shared knowledge artifact such as a shared data model known as Enterprise Data Model (covering the entire suite of use-cases and domains and business units).
`neat` has been designed to facilitate this process by providing a way to iterate on and developed an enterprise data model.

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

| Class       | Property             | Description | Value Type    | Min Count | Max Count |
|-------------|--------------------- | ----------- |-------------- |-----------|-----------|
| WindTurbine | name                 |             | string        | 1         | 1         |
| WindTurbine | location             |             | string        | 1         | 1         |
| WindTurbine | manufacturer         |             | string        | 1         | 1         |
| WindTurbine | lifeExpectancy       |             | float         | 0         | 1         |
| WindTurbine | ratedPower           |             | float         | 1         | 1         |
| WindTurbine | hubHeight            |             | integer       | 1         | 1         |
| WindTurbine | actualPower          |             | float         | 0         | 1         |
| WindTurbine | arrayCableConnection |             | integer       | 1         | 1         |

In each row of the `Properties` sheet, Jon will define a statement. For example, the first row says that a
`WindTurbine` has a `name`. In addition, Jon can add a `description`, i.e., a human-readable explanation of what a particular property means. The three next columns help the information architect, David, to understand how to model the data. First, we have the
`Value Type` column, which specify what type of data this statement is about. Is this a number, an on/off value, text,
or something else? In this case, the `name`, `location`, and `manufacturer` are all strings, meaning they are
expected to be text. The `Min Count` and `Max Count` columns specify how many data points are expected for each of these properties. In the
first row, we see that a `WindTurbine` is expected to have exactly one `name`. Sames goes for the `location` and `manufacturer`. However, for `lifeExpectancy`, we see that it is optional, as the `Min Count` is 0. Also, `lifeExpectancy` is a float, as it is expected to be a number.


In the similar fashion, Jon defines the properties for `WindFarm`, `Substation` and `ExportCable` in the `Properties` sheet.

In addition to the `Properties` sheets, `neat` also requires one more sheet `Metadata` for domain experts.
In case of domain expert the `Metadata` sheet only requires `role` and `creator` to be set, where `role` represent the role a person has in modeling of the enterprise data model and `creator` is the name of the person from whom we are acquiring knowledge to create the model.
For Jon the `Metadata` sheet looks as follows:

|         |               |
|---------|---------------|
| role    | domain expert |
| creator | Jon           |


Download Jon's spreadsheet from [here](insert link).


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
Similarly to Jon, Emma will define a set of statements in a spreadsheet. For example, she might define that a
`Substation` has a `name`, a `location`, and a `voltage`. In addition, she might define that a `Substation` has
a `transformer` and a `circuit breaker`, and she has also added a `WindGenerator` that has a name.
The `Properties` sheet for Emma might look as follows:

| Class         | Property        | Description | Type           | Min Count | Max Count |
|---------------|-----------------| ----------- |----------------|-----------|-----------|
| Substation    | name            |             | string         | 1         | 1         |
| Substation    | location        |             | string         | 0         | 1         |
| Substation    | voltage         |             | timeseries     | 1         | 1         |
| Substation    | transformer     |             | Transformer    | 1         | 1         |
| Substation    | circuit breaker |             | CircuitBreaker | 1         | 1         |
| WindGenerator | name            |             | name           | 1         | 1         |


Furthermore, Emma might define the `Substation` class as follows:

| Class          | Description                                       | Parent Class |
|----------------|---------------------------------------------------|--------------|
| Substation     | A part of an electrical grid                      |              |
| Transformer    | A device that changes the voltage of electricity  | Substation   |
| CircuitBreaker | A device that can stop the flow of electricity    | Substation   |

You can find the complete `Properties`, `classes`, and `metadata` sheets for Emma here.

Finally, Emma will validate her sheet using the `neat` UI, just like Jon did.

|         |               |
|---------|---------------|
| role    | domain expert |
| creator | Jon           |



In the `Properties` sheet, we introduce the concept of a `Class`. Classes are used to group properties that define a thing. For example, a `WindTurbine` is a class, and the set of properties for a class defines what it means to be a member of that class.

For example, Jon might define the `WindTurbine` class as follows:

| Class       | Description                                         | Parent Class |
|-------------|-----------------------------------------------------|--------------|
| WindTurbine | A device that converts wind to electrical energy    |              |
| Nacelle     | The covering house of all the generating components | WindTurbine  |
| Rotor       | The rotating part of the wind turbine               | WindTurbine  |

In addition, to `Class` and `Description` columns, we have a `Parent Class` column. This column is used to define
that a hierarchy of classes. For example, Jon has defined that a `Nacelle` and a `Rotor` are both types of a `WindTurbine`.
This column is optional, and if a class does not have a parent class, we leave the cell empty.

In the `Types` column in the `Properties` sheet, we can use basic types like `string`, `number`, `boolean`, `date`,
`timeseries`, but in addition we cal also use classes. For example, after Jon has defined the `Nacelle` and `Rotor`
classes, he can now go back to the `Properties` sheet and define that a `WindTurbine` has a `nacelle` and a `rotor`.

| Class       | Property     | Description | Type       | Min Count | Max Count |
|-------------|--------------| ----------- |------------|-----------|-----------|
| WindTurbine | name         |             | string     | 1         | 1         |
| WindTurbine | location     |             | string     | 0         | 1         |
| WindTurbine | manufacturer |             | string     | 0         | 1         |
| WindTurbine | nacelle      |             | Nacelle    | 1         | 1         |
| WindTurbine | rotor        |             | Rotor      | 1         | 1         |

Note that the above two statements defines the relationship between the `WindTurbine` class and the `Nacelle` and `Rotor`.


### Summary

**Domain Expert Task.**

1. (Required) Gathering statements in a spreadsheet.
2. (Optional) Defining classes in a spreadsheet.

**Domain Expert usage of `neat`**:

1. Validate the sheet using the `neat` UI.


## Information Architect: David

### Creating the Shared Data Model

Once Jon and Emma have defined their statements, David will combine the two sheets into a single sheet. This is
done by simply copying the statements from Jon and Emma into a single sheet. For example, the `Properties` sheet
for David might look as follows:

| Class         | Property         | Description | Type           | Min Count | Max Count |
|---------------|------------------| ----------- |----------------|-----------|-----------|
| WindTurbine   | name             |             | string         | 1         | 1         |
| WindTurbine   | location         |             | string         | 0         | 1         |
| WindTurbine   | manufacturer     |             | string         | 0         | 1         |
| WindTurbine   | nacelle          |             | Nacelle        | 1         | 1         |
| WindTurbine   | rotor            |             | Rotor          | 1         | 1         |
| Substation    | name             |             | string         | 1         | 1         |
| Substation    | location         |             | string         | 0         | 1         |
| Substation    | voltage          |             | number         | 1         | 1         |
| Substation    | transformer      |             | Transformer    | 1         | 1         |
| Substation    | circuit breaker  |             | CircuitBreaker | 1         | 1         |
| WindGenerator | name             |             | name           | 1         | 1         |

In addition, David will also need to combine the `classes` sheets from Jon and Emma. This is done by simply
copying the statements from Jon and Emma into a single sheet. For example, the `classes` sheet for David might

| Class           | Description                                         | Parent Class |
|-----------------|-----------------------------------------------------|--------------|
| WindTurbine     | A device that converts wind to electrical energy    |              |
| Nacelle         | The covering house of all the generating components | WindTurbine  |
| Rotor           | The rotating part of the wind turbine               | WindTurbine  |
| Substation      | A part of an electrical grid                        |              |
| Transformer     | A device that changes the voltage of electricity    | Substation   |
| CircuitBreaker  | A device that can stop the flow of electricity      | Substation   |

In addition, David will need to create a `metadata` sheet for himself, where he sets the
knowledge into context. He would have to add the following rows to the `metadata` sheet:

|             |                       |
|-------------|-----------------------|
| role        | information architect |
| prefix      | power                 |
| namespace   | pwr                   |
| version     | 1                     |
| contributor | Jon, Emma, David      |
| created     | 2021-01-01            |
| updated     | 2021-01-01            |

In the `metadata` sheet, David has added a `prefix` and a `namespace`.

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

### Implementing the Shared Data Model
Neat supports exporting a data model to CDF either using an `AssetLoader` or `DMSLoader`. The `AssetLoader` is
used to load the data model into the classical `AssetHierarchy` in CDF, while the `DMSLoader` is used to load the
data model into the new Data Modeling Service (DMS) in CDF. The `DMSLoader` is the recommended way to load the
data model into CDF, as it supports more advanced features such as defining dependencies between data. In this
tutorial, we will focus on the `DMSLoader`.

Once David has defined the shared data model, Alice will implement it in CDF. The focus of Alice is to make sure
that the shared data model is implemented in CDF in a way that accounts for the expected usage of the data. For example, she
needs to define how the data is stored and what properties are indexed for fast search. In addition, she decides
which dependencies between data should be enforced. This is a trade-off in that being very strict on the data
makes it easy to use as it is predictable. However, it can be hard to populate it as large quantities of the
data might not be in the expected format. On the other hand, being very flexible on the data puts a higher burdon
on the developers/users that use the data.

First, Alice has to modify the `metadata` sheet to include the CDF specific information.

|             |                         |
|-------------|-------------------------|
| role        | dms architect           |
| prefix      | power                   |
| namespace   | pwr                     |
| space       | sp_power                |
| externalIdc | power_enterprise_model  |
| version     | 1                       |
| contributor | Jon, Emma, David, Alice |
| created     | 2021-01-01              |
| updated     | 2021-01-01              |

First, she adds herself as a contributor, and then she adds the `space` and `externalIdc` columns. The `space`
column is used to define the space in CDF where the data model should be loaded. The `externalIdc` column is used
to define the external id of the data model. This is used to reference the data model from other parts of CDF.

### Extending the <code>properties</code> Sheet

In addition, Alice will add four new columns to the `Properties` sheet. The `container` and `containerProperty`
are used to specify which container and property the data should be stored in. The `index` column is used to specify
whether it should be part of an index, and finally the `constraints` column is used to specify any constraints.

| Class         | Property         | ... | container | Container Property | Index | Constraints |
|---------------|------------------|-----|-----------|--------------------|-------| ----------- |
| WindTurbine   | name             |     | asset     | name               | name  |             |

TODO How views are handled.

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
