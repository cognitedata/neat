# Knowledge Acquisition

This tutorial covers how to use `neat` for knowledge acquisition and produce a shared data model in
Cognite Data Fusion (CDF).

## Introduction

Companies typically have multiple domain experts that cover different areas of the business. Typically, these
areas are partially overlapping, both in concepts and data. Lots of the value in a product like CDF comes from
taking data from different sources and making it easily accessible and understandable for all domain experts, as
this unlocks the potential for cross-domain insights.

Knowledge acquisition is the process of taking the knowledge from domain experts and turning it into a shared
data model. `neat` has been designed to facilitate this process by providing a way to define a shared data model.

## Use Case

In this tutorial, we will focus on the Power & Utilities industry. We will have two domain experts, one that
focuses on wind turbine maintenance and one that focuses on grid analysis, lets call them Jon and Emma. In addition,
we will have a data engineer, let's call him David, who will be responsible for combining the knowledge from Jon and
Emma into a shared data model. Finally, we have a CDF expert, let's call her Alice, who will be responsible for
implementing the shared data model in CDF. Note that in a real-world scenario, the data engineer and the CDF expert
might be the same person, but for the purpose of this tutorial, we will keep them separate to highlight that their
required skills are different.

**Note** You don't need to be an expert in the Power & Utilities industry to follow this tutorial. The concepts
are generic and can be applied to any industry in which you have domain experts with overlapping knowledge and data.

## Wind Turbine Maintenance Expert: Jon

### Gathering Knowledge
In `neat`, knowledge is captured in statements. A statement is a simple fact. We will often refer to it as a `property`.
For example, Jon might say that a wind turbine has a `name`, a `location`, and a `manufacturer`. These are all
statements. In `neat`, we capture these statements in a spreadsheet format. We refer to a set of
statements as `properties`. The `properties` sheet looks as follows for a domain expert like Jon:

| Class       | Property     | Description | Type   | Min Count | Max Count |
|-------------|--------------| ----------- |--------|-----------|-----------|
| WindTurbine | name         |             | string | 1         | 1         |
| WindTurbine | location     |             | string | 0         | 1         |
| WindTurbine | manufacturer |             | string | 0         | 1         |

In each row of the `properties` sheet, Jon will define a statement. For example, the first row says that a
`WindTurbine` has a `name`. In addition, Jon can add a `description`, i.e., a human-readable explanation of the
statement. The three next columns help the data engineer, David, to understand how to model the data. First, we have the
`Type` column, which specify what type of data this statement is about. Is this a number, an on/off value, text,
or something else? In this case, the `name`, `location`, and `manufacturer` are all strings, meaning they are
expected to be text. The `Min Count` and `Max Count` columns specify how many data points are expected. In the
first row, we see that a `WindTurbine` is expected to have exactly one `name`. In the second and third row, we see
that a `WindTurbine` can have zero or one `location` and `manufacturer`. In other words, we these two properties
are optional. Even though all `WindTurbines` have a manufacturer, Jon knows that we do not always have this
information, so he has specified that it is optional.

In the `properties` sheet, we introduce the concept of a `Class`. Classes are used to group properties, and the
set of properties for a class defines what it means to be a member of that class. In `neat`, classe have
their own sheet, where we define the class and its description. For example, Jon might define the `WindTurbine`
class as follows:

| Class       | Description                                         | Parent Class |
|-------------|-----------------------------------------------------|--------------|
| WindTurbine | A device that converts wind to electrical energy    |              |
| Nacelle     | The covering house of all the generating components | WindTurbine  |
| Rotor       | The rotating part of the wind turbine               | WindTurbine  |

In addition, to `Class` and `Description` columns, we have a `Parent Class` column. This column is used to define
that a hierarchy of classes. For example, Jon has defined that a `Nacelle` and a `Rotor` are both types of a `WindTurbine`.
This column is optional, and if a class does not have a parent class, we leave the cell empty.

In the `Types` column in the `properties` sheet, we can use basic types like `string`, `number`, `boolean`, `date`,
`timeseries`, but in addition we cal also use classes. For example, after Jon has defined the `Nacelle` and `Rotor`
classes, he can now go back to the `properties` sheet and define that a `WindTurbine` has a `nacelle` and a `rotor`.

| Class       | Property     | Description | Type       | Min Count | Max Count |
|-------------|--------------| ----------- |------------|-----------|-----------|
| WindTurbine | name         |             | string     | 1         | 1         |
| WindTurbine | location     |             | string     | 0         | 1         |
| WindTurbine | manufacturer |             | string     | 0         | 1         |
| WindTurbine | nacelle      |             | Nacelle    | 1         | 1         |
| WindTurbine | rotor        |             | Rotor      | 1         | 1         |

Note that the above two statements defines the relationship between the `WindTurbine` class and the `Nacelle` and `Rotor`.

In addition to the `properties` and `classes` sheets, `neat` also requires one more sheet `Metadata` for domain experts.
The `Metadata` sheet is used to define the domain expert's name, the date of the knowledge acquisition, and a description
of the domain expert's knowledge. This is useful for the traceability of the knowledge acquisition process.

|         |               |
|---------|---------------|
| role    | domain expert |
| creator | Jon           |

You can find the complete `properties`, `classes`, and `metadata` sheets for Jon here.

### Validating Statements
When Jon has defined all the statements, he can validate the sheet using `neat`. This will check that all the
statements are correctly defined and that there are no inconsistencies. For example, that all Types are defined
have been defined in the `classes` sheet.

To validate his sheet, Jon opens the `neat` UI and selects the `Validate Rules` workflow:

<img src="images/validate_workflow.png" height="300">

Then, his sheet is named `jon_wind_turbine.xlsx`, and he needs to go into the `Validate Rules` step and
change the configuration to point to his sheet:

<img src="images/change_validate_step.png" height="300">

Finally, he can click the `RunWorkflow` button to validate his sheet and it will outut a report with any errors
and warnings.

<img src="images/run_workflow.png" height="300">

## Grid Analysis Expert: Emma

## Data Engineer: David

## CDF Expert: Alice
