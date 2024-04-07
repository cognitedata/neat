# Extending the Enterprise Model

This tutorial demonstrates how to extend the Enterprise model. Extending a model means changing it
by adding, changing, or removing any of its elements **after it hs been put in production**.

We assume that there is already an enterprise model developed, as in the
[Knowledge Acquisition](./part-1-knowledge-acquisition.md) tutorial, which will be the one we extend. In addition,
the source for the extension is the solution model developed in the [Solution Modeling](./part-2-analytic-solution.md)
tutorial.

## Introduction

Svein Harald is the head information architect at `Acme Corporation`. He has the ultimate responsibility for the
enterprise model. Olav and his team have now developed a successful timeseries forecast model for power production the
wind turbines at `Acme Corportation`, and the trading department is now eager to start using these new
forecast when making decisions on when trading power. Svein Harald has been tasked with helping Olav and his team
share their result with the trading department and the rest of the organization.

## Why Extend the Enterprise Model?

Olav suggests that the simplest way to share the forecast with the trading department is to just give them access to the
forecast solution model and let them use it directly. Svein Harald is not so sure. He is concerned that the forecast
solution model is too detailed and complex for the trading department to use directly. It, for example, contains a
lot of technical information such as the exact parameters of the machine learning model, which is not
relevant for the trading department.

The second suggestion from Olav is to create a new model on top of the forecast solution model that is a subset with
only what is relevant for the trading department. Again, Svein Harald is not so sure. He points out that, even though
this works well for this specific case, it will not scale well. If every department in the organization creates their
own solution models on top of other solution models, it will easily become a lot of duplicated information and
inconsistencies between the models and ultimately enable silos in the organization.

Instead, Svein Harald suggests that they extend the enterprise model with the relevant part of the forecast solution
model. He explains that even though this will be a slightly slower process as more clarification and discussion will likely
be required. It is exactly this clarification and discussion that breaks down the silos in the organization and aligns
the departments to obtain a shared understanding of the data and the models. Olav understands the point and eagerly
agrees to work with Svein Harald to extend the enterprise model.

## How to Extend the Enterprise Model?

When extending the Enterprise model, it is important to try to avoid doing changes that will require changes in the
solution models and use cases that are built on top of the enterprise model. In `Acme Corporation`, there are already
10 solution models powering 25 use cases that are built on top of the enterprise model. If the Enterprise model changes
such that these must be updated, it will be very costly for the organization.

**NEAT** provides three ways to extend any data model depending on the impact of the changes:

* **Additive Changes**: Adding new elements to the model. This is the least intrusive change and will not require
  changes in the solution models or use cases.
* **Reshape Changes**: Changing the structure of the model. This is a more intrusive change and may require changes in
  the solution models and use cases.
* **Rebuild Changes**: Changing the semantics of the model. This is the most intrusive change and will require changes
  in the solution models and use cases. In addition, it may also require data migration.

When Svein and Olav are working on the extension, they identify that the changes they are introducing are
Additive Changes as they are adding new forecast elements to the enterprise model.

Thus, in this tutorial, we will only focus on **Additive Changes**. However, what follows are a few examples of
changes that could lead to **Reshape Changes** and **Rebuild Changes**:

* **Renaming of a Concept**. For example, if `Acme Corportation` have been using the term `Power Production` and
  `Power Consumption` in the enterprise model, and they now want to change this to `Energy Production` and
  `Energy Consumption`, this would be a Reshape Change.
* **Changing Type**. For example, in the `WindTurbine`, `ratedPower` is modeled as a `float` and this should de changed
   to a `timeseries`. This would be a Rebuild Change.

**Note** in the last example, if no use cases and solution models are using the `ratedPower` attribute, it would
be a much cheaper change to make than if it was used in many places.

Svein Harald starts by using **NEAT** to download the enterprise model. He opens **NEAT** and selects the `Import DMS`
workflow, and then clicks on the `Import DMS` step. This opens the modal with the configuration for the import

<img src="../../artifacts/figs/life_cycle_download_reference_model_analytic_soluteion_model.png" height="300">

Svein Harald selects the following options:

* **Data model id**: This is the id of the enterprise model. Svein Harald finds this ID by login into CDF.
* **Report formatter**: This is used in the validation of the model. The enterprise model should be valid,
  so this is likely not needed.
* **Role**: This is which format Svein Harald wants to download the model. He selects `information_architect`. This is
  because he wants to focus in the modeling and not the implementation of the model.
* **Reference**: This is whether the imported model should be used as a reference model. Svein Harald sets this to
  true as the current Enterprise Model is a reference model for the extension. This will be used in the validation
  by **NEAT** to ensure that the extension is consistent with the enterprise model.

After clicking `Save` and `Save Workflow`, Svein Harald runs the workflow by clicking `Start Workflow`. The workflow
will execute and SveinHarald can download the exported model by clicking `exported_rules_information_architect.xlsx`.
Note that `rules` is the **NEAT** representation of a data model.

The downloaded spreadsheet contains six sheets:

* **Metadata**: This contains the metadata for the additions to the Enterprise model, and will only have headings
  (see definition of headings [here](../../terminology/rules.md#metadata-sheet))
* **Properties**: This contains the properties for the changes, and will only have headings
  (see definition of headings [here](../../terminology/rules.md#properties-sheet))
* **Classes**: This contains the classes for the changes, and will only have headings
  (see definition of headings [here](../../terminology/rules.md#classes-sheet))
* **RefProperties**: This will be all the properties from the enterprise model that Svein Harald can use to lookup
  what properties he wants to use in the solution model. In addition, this will be used in the validation
  of the solution model.
* **RefClasses**: This will be all the classes from the current enterprise model. Similar to the `RefProperties`,
  this will be used to look up, and will be validated
  against.
* **RefMetadata**: This will be the metadata from the current Enterprise model.

## Setting up the Metadata for the Extension

Svein Harald starts by setting up the metadata for the extension. He opens the `Metadata` sheet in the spreadsheet
and fills in the following information:


|             |                                |
|-------------|--------------------------------|
| role        | information architect          |
| creator     | Svein Harald, Olav             |
| namespace   | http://purl.org/cognite/power  |
| prefix      | power                          |
| schema      | extended                       |
| extension   | addition                       |
| created     | 2024-03-26                     |
| updated     | 2024-04-07                     |
| version     | 0.1.0                          |
| title       | Power to Consumer Data Model   |
| description |                                |

The most important part of the metadata sheet is the `prefix`, `schema` and `extension`. The `prefix` is the same as
the `prefix` in the enterprise model and `schema` is set to `extension`. This is used to tell **NEAT** that this
is an extension of the enterprise model. In addition, the `extension` is set to `addition` this tells **NEAT** what
kind of extension this is and thus how it should be validated. This way Svein Harald and Olav can be sure that they
are not doing a reshaping or rebuilding of the enterprise model by accident.

For more information on the metadata sheet, see [here](../../terminology/rules.md#metadata-sheet).

## Adding new Concepts to the Enterprise Model

Olav tells Svein Harald that it is the timeseries forecast for the `WindTurbine` and `WindFarm` that is relevant for
the trading department. There is no need to include the `TimeseriesForecast` and `WeatherStation` in the enterprise
model from the forecast solution model.

Note here that Svein Harald and Olav are here following a principle of including only the bare minimum of
what is needed by the trading department. This is to keep the complexity of the Enterprise model down. In addition, if
they had included the `TimeseriesForecast` and `WeatherStation` in the enterprise model now, but later decided they
actually needed these in the Enterprise model, however, slightly modified, they would have to do a reshape, or
even rebuilding, of the model, which could be costly. Now, they have more flexibility if they later decide they need
these in the Enterprise model later. A good rule of thumb is to have a concrete use case for including a concept in the
Enterprise model.

Olav have gathered the following six properties from the forecast solution model that he wants to include in the
enterprise model:

| Class       | Property              | Value Type | Min Count | Max Count | ... | Reference |
|-------------|-----------------------|------------|-----------|-----------|-----|-----------|
| WindTurbine | minPowerForecast      | timeseries | 0         | 1         |     |           |
| WindTurbine | mediumPowerForecast   | timeseries | 0         | 1         |     |           |
| WindTurbine | maxPowerForecast      | timeseries | 0         | 1         |     |           |
|             |                       |            |           |           |     |           |
| WindFarm    | lowPowerForecast      | timeseries | 0         | 1         |     |           |
| WindFarm    | highPowerForecast     | timeseries | 0         | 1         |     |           |
| WindFarm    | expectedPowerForecast | timeseries | 0         | 1         |     |           |

Svein Harald thinks this is a good start, but he realizes that there are some opportunities for improvement.

* **Missing Concept**: There seems to be a missing concept in the forecast solution model. We see that it is three
  very similar properties for the `WindTurbine` and `WindFarm`. Svein Harald suggest that they should introduce a
  concept to capture this. He suggests that they introduce a new concept called `TimeseriesForecastProduct`.
* **Inconsistencies***: Even though it is three similar properties for the `WindTurbine` and `WindFarm`, the names
  are different. `min`, `medium`, and `max` for the `WindTurbine` and `low`, `high`, and `expected` for the `WindFarm`.
  By introducing the `TimeseriesForecastProduct`, they can make the names consistent.
* **Extensibility**: Svein Harald also realizes the new concept `TimeseriesForecastProduct` is likely to be extended
  in the future, for example, with a `confidence` property.
* **Modeling**. In the forecst solution model, the forecast is modeled on the `WindTurbine` and `WindFarm`. Svein
  Harald, however, decides that power production forecast are more generic concepts so he decides to add it to the
  parent classes `GeneratingUnit` and `EnergyArea` instead. This way, the Enterprise model is ready for forecast of
  other types of generating units and energy areas in the future.

Svein Harald starts by adding the new concepts to the `Properties` sheet in the spreadsheet. He adds the following
rows:

| Class                     | Property      | Value Type                |
|---------------------------|---------------|---------------------------|
| TimeseriesForecastProduct | low           | timeseries                |
| TimeseriesForecastProduct | expected      | timeseries                |
| TimeseriesForecastProduct | high          | timeseries                |
|                           |               |                           |
| EnergyArea                | powerForecast | TimeseriesForecastProduct |
|                           |               |                           |
| GeneratingUnit            | powerForecast | TimeseriesForecastProduct |

With the new class `TimeseriesForecastProduct`, Svein Harald also adds the new class to the `Classes` sheet in the
spreadsheet. He adds the following row:

| Class                     | Parent Class |
|---------------------------|--------------|
| TimeseriesForecastProduct |              |

## Updating the Spreadsheet (Download Svein Harald's Information spreadsheet)

Svein Harald adds the new concepts to the `Properties` and `Classes` sheets in the spreadsheet.

You can download Svein Harald's spreadsheet [here with the information model](../../artifacts/rules/information-addition-svein-harald.xlsx).


## Implementing the Extension

## Updating the Spreadsheet (Download Olav's DMS spreadsheet)

## Deploying the Extension

## Summary

**Information Architect usage of NEAT**:

1. Download the enterprise model.
2. Validate extension against existing enterprise model.
3. Deploy the extension.
