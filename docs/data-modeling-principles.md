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
3. Parsimonious Model. Data models should be as simple as possible, but not simpler.

## Best Practices

1. Establish a data governance team that will ensure implementation of the best practices
2. Create one main data model, the Enterprise Data Model, that is shared across the organization.
3. Each business area can create one or more specific data models based on the Enterprise Data Model, called
   Solution Data Models.
4. Solution Data Models should always be referencing the Enterprise Data Model, not another Solution Model.
5. All data models are kept in its own `Space`, thus data models do not share the same `Space`.
6. All `View`s of a data models have the same version and `Space` as the data model.
7. Keep the Enterprise Data Model as small as possible, but not smaller.

## Justification

### Data models should be designed for real use cases

A danger with data modeling is that it can become an academic exercise with a lot of discussions about what to
name concepts and how the concepts should be related to each other. In addition, there is a danger of creating
extremely detailed data models, which are 1–1 representation of the real and digital world, but data models
which have poor performances and are only understandable to the few who build them.
Having real use cases is what grounds the modeling effort in reality and ensures that the data model is useful
for the organization. Often is a good practice start with three relevant business questions to be answered
and drive the data modeling process from them.

### The essence of data modeling is **cooperation**

Data modeling is how people with different backgrounds and perspective come together to create a shared understanding
of the business and data. You should expect that there will be friction in this process as it surfaces and makes
concrete the understanding from different parts of the organization. It is by working through this friction that
the organization creates the shared understanding that unlocks better collaboration across the organization,
resulting in solving critical business questions.

### Parsimonious Model

The principle of parsimony is a fundamental principle in science and engineering. It states that a model should be
as simple as possible, but not simpler. In the case of an Enterprise Data Model, it should contain all shared
concepts across the organization, but no concepts that are only relevant for a single business area.

### Establish a data governance team
This follows from the principle of cooperation. This team should be cross-functional and have representatives
from all relevant parts of the organization. This is important to ensure that the Enterprise Data Model
has a solid anchoring in the organization such that it will be used and maintained.

### Create one main data model, the Enterprise Data Model

This follows from the principle of cooperation. By having one main data model, it forces the organization to
cooperate. Once the Enterprise Data Model is in place, it serves as the foundation for cooperation across the
organization. It also explicitly encodes implicit knowledge, making it clearer and easier to discuss,
onboard new employees and partners, and to make decisions. The Enterprise Data Model forms a singular language
for communication among various business units and subdomains.

### Each business area can create one or more specific data models

This follows from the principle of cooperation and parsimonious model. The development of the
Enterprise Data Model will necessarily be a slower process, and it typically will become a larger data model
that can be challenging to use for practical applications. A Solution Data Model is a business area / subdomain-specific
data model using a subset of the Enterprise Data Model, which can also be extended with additional concepts that are
not part of the Enterprise Data Model. This allows business areas to move faster and to adapt the data model
to their specific needs. It is also a typical way to test new concepts before they are integrated into
the Enterprise Data Model. Also, the solution model will have higher fidelity of details specific for a business
unit / subdomain.  Furthermore, while at the Enterprise data model level all parties need to agree on an enterprise
level naming convention, which means a lot of compromises, at the Solution data model level a business unit can use
their subdomain-specific naming convention, thus the business unit has more freedom.

### Solution Data Models should always be referencing the Enterprise Data Model

This follows from the principle of cooperation and parsimonious model. The trade-off that the Enterprise and
Solution data models are trying to balance is between *cooperation* and the *ability to move fast*. If the organization
only had a single data model, development would be extremely slow and many concepts would be irrelevant for
most parts of the organization. On the other hand, if each business area had its own data model,
it would be very challenging to cooperate across the organization, a situation which we refer to as *siloing* as data,
information and knowledge among various business units would be isolated.
If Solution Data Models are allowed to build on top of other Solution Data Models, it increases the complexity
which makes it hard to maintain and understand. In addition, it can easily lead ot siloing through obfuscation.
By using the Enterprise Data Model for shared concepts, it enforces a discussion when new concepts are introduced.
The discussion will ensure that the new concepts are well anchored in the organization and can be built upon by other
business areas.

### All data models are kept in its own `Space`

This follows from the principle of parsimonious model. By keeping each data model in its own `Space`, it is clear
which concepts are part of the data model and which are not. It also makes it easier to manage access control,
which should be with the team that owns the data model. In addition, this enables establishing a clear
portfolio of data products an organization owns.

### All `View`s of a data models have the same version and `Space` as the data model

This follows from the principle of parsimonious model. Technically, a data model can contain `View`s from
different `Space`s and with different version. However, `View`s are very cheap and having `View`s with different
versions than the data model can cause a lot of confusion. Furthermore, all `View`s should be controlled by the
team that owns the data model, thus they should be in the same `Space`. If a solution models needs to use a `View`
that is identical to a `View` in the Enterprise Data Model, you should use the `implements` option to reference the
`View` in the Enterprise Data Model. An advantage of this is that if you want to extend the `View` later
in the Solution Data Model, you can do that without affecting the `View` in the Enterprise Data Model.

### Keep the Enterprise Data Model as small as possible, but not smaller

This follows from the principle of cooperation and parsimonious model. There is a cost to each concept in the
Enterprise data model as it needs to be discussed and anchored in the organization. Thus, concepts that are not
shared should not be put through this process. A side note is that concepts that are not shared can easily
elicit strong opinions without grounding in reality, and thus be an extra long cumbersome waste of time.

In addition, the organization will constantly evolve the Enterprise Data Model, and the goal is to avoid
introducing changes that will lead to a chain of changes to all Solution Data Models. If we avoid introducing
a new concept too early, it gives us the maximum flexibility in the future when we need to introduce the new concept.
If the concept is already in the Enterprise Data Model, it will be much more costly to change it.

Note that an organization that is mature when it comes to data modeling should expect to have three versions of the
Enterprise Data Model: `legacy`, `current` and `future`. The `current` is the version that most solution models
are using, the `legacy` is the version that is being phased out, and the `future` is the version that is currently
being developed thus is still subject to change. One should aim at developing data models that are forward compatible,
enabling migration to the latest version with no issues if possible.
