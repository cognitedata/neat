# Overview

In this set of tutorials, we will walk you through the data modeling lifecycle and how **NEAT** can assist in the
different tasks involved in building and maintaining data models. But first, let's understand what data modeling
is and why it is important.

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

- **[Extending Enterprise Model](./part-3-extending-enterprise-model.md)**: In this tutorial, you will learn how to extend
  the enterprise model while keeping the existing model intact. In this tutorial, we will add new concepts discovered
  during the implementation of the forecasting use case.

- **[Extending Solution Model](./part-4-extending-solution-model.md)**: In this tutorial, you will learn how
  to extend the solution model while keeping the existing model intact. In this tutorial, we will add new concepts
  discovered during the implementation of the forecasting use case.

- **[Business Solution Model](./part-5-business-solution-model.md)**: In this tutorial, you will learn how to
  use the Enterprise Model to build a Solution Model for a business case. This data model will only use a subset
  of the Enterprise Model and not add any new concepts. It is intended for a business user that only needs to select
  the part of the Enterprise Model that is relevant for their business case.
