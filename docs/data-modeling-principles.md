# Data Modeling Principles

This document contains a list of principles and best practices for data modeling within an organization. These
principles are not strict rules, but it is an attempt to provide a concise set of guidelines based on
the most up-to-date experience of the **NEAT** team. Note that several of the best practices are
implemented into **NEAT** and you will get warnings if you do not follow them.

This document first presents the principles and then the best practices without justification. This is to provide
a quick reference for the reader. The justification for each principle and best practice is provided in the
[Justification](#justification) section.

**Pre-requisites**: This document assumes that the reader is familiar with the Cognite Data Fusion (CDF) data modeling
concepts `Space`, `Data Model` and `View`.

## Principles

1. Data models should be designed for real use cases, not for the sake of modeling alone.
2. The essence of data modeling is **cooperation**: It is how people work together to create a shared understanding
   of the business and data.

## Best Practices

1. Create one main data model, the Enterprise Data Model, that is shared across the organization.
2. Each business area can create one or more distributed data models based on the Enterprise Data Model, called
   Solution Data Models.
3. Solution Data Models should always be referencing the Enterprise Data Model, not another Solution Model.
4. All data models are kept in its own `Space`, thus data models do not share the same `Space`.
5. All `View`s of a data models have the same version and `Space` as the data model.
6. Keep the Enterprise Data Model as small as possible, but not smaller.

## Justification
