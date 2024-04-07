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

## Download the Current Enterprise Model

## Adding new Elements to the Enterprise Model
