# Overview

!!! warning annotate "Warning"

    This set of tutorials are work in progress, and there might be minor changes to the completed ones while others
    are being developed. We appreciate your understanding and patience.

In this set of tutorials, we will walk you through the data modeling lifecycle and how **NEAT** can assist in the
different tasks involved in the lifecycle. But first, let's understand what data modeling is and why it is important.

Ultimately, the goal of data modeling is to use data to aid decision-making. To achieve this, a company
needs to coordinate between multiple different people and departments. A set of data models can be used as
the common language to share information and provide context for data such as timeseries and documents. The
data models can then be used as the basis for multiple different applications/solutions/reports that are used to make
decisions. Simply put: **Data modeling is cooperation**.

In this set of tutorials, we will focus on a fictions company, `Acme Corporation`, that works in the Power & Utilities
industry. You don't need to know anything about the Power & Utilities industry to follow along. The tutorials will
provide you with all the information you need to understand the domain and the data model that we will build. The
tutorials will focus on all parts of the data modeling lifecycle process, from gathering information, taking advantage
of existing standards, building an enterprise model, build models for specific use cases, extending existing data
models. You can follow the tutorial in any order. In addition, you can use
[User Personas](./user-personas.md) as a lookup to get the structure of the `Acme Corporation` and the user
personas that will be used in the tutorials. **Note** the tutorials covers a large spectrum of tasks and roles, which
includes many concepts. It is not intended that a single person should be able to do all the tasks, but rather that
different people with different roles can work together to achieve the goal of building a data model.


- **[Knowledge Acquisition](./part-1-knowledge-acquisition.md)**: In this tutorial, you will learn how to gather information
  about the business requirements and the data sources that will be used to build the data model from the domain experts,
  crafting an enterprise data model that represents the business requirements and the data sources. The enterprise
  data model is fine-tuned by the solution architects to ensure that it technically aligns with the organization's data
  infrastructure, such as Cognite Data Fusion.

- **[Analytic Solution](./part-2-analytic-solution.md)**: In this tutorial, you will learn how to build a solution model
  for a forecasting use case. The solution model is using a subset of the enterprise model and, in addition, adds
  new concepts that are needed for the forecasting use case.
