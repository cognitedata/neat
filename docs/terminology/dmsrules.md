# DMS Rules Details

## View

### Filter
Filters are used to specify which nodes or edges should be returned when querying a view. This is difficult to
set manually, thus, unless you know what you are doing, we recommend using the default set by **NEAT**. You select
the default by leaving the filter empty.

#### What is supported?
While **NEAT** DMSRules are one-to-one with the CDF API specification for creating Data Models, the view filter is the
exception. If you compare to the [API specification for views](https://api-docs.cognite.com/20230101/tag/Views/operation/ApplyViews)
you will notice that `filter` is a very flexible parameter were you can specify an arbitrary complex filter.
**NEAT** has an opinionated approach to creating the view filter.

**NEAT** supports two filters

* `hasData` in `containers` - This filter returns all nodes/edges that have data in the specified containers.
* `NodeType` filter - This filter returns all nodes of a specific type. **NEAT** supports specifying multiple node types.

#### Default Filter (Smart Defaults)

The default filter set by **NEAT** is set based on the data model type, whether the view is mapping to containers or not, and
whether the view is mapping to containers in another data model.

* If the data model type is `solution` and the view has properties mapping to containers in an enterprise data model,
  the default filter is `nodeType` filter with all node ids matching the id of the container in the enterprise data model.
* If the data model type is `solution` and the view has properties mapping only to containers in the same data model,
  the default filter is `hasData` filter with all containers in the data model.
* If the data model is `enterprise` and the view has properties mapping to containers, the default filter is `hasData` filter
  with all containers mapped to by the view.
* If the data model type is `enterprise` and the view has no properties mapping to containers, the default filter is `NodeType`
  filter with the same node id as the view.

Looking at Olav's solution model, from the [Analytic Solution Tutorial](../tutorials/data-modeling-lifecycle/part-2-analytic-solution.md#implementing-the-solution-model),
the `WindTurbine` and `WindFarm` views are referencing containers in the enterprise data model, so these
will have a `nodeType` filters `nodeType(power:GeneratingUnit,powerWindTurbine)` and `nodeType(power:EnergyArea,power:WindFarm)` respectively.

If we look at the enterprise data model, from the [Knowledge Acquisition Tutorial](../tutorials/data-modeling-lifecycle/part-1-knowledge-acquisition.md#dms-architect-alice),
the most of the views will use a `hasData` filter, for example, the wind turbine will use the filter
`hasData(power:GeneratingUnit, powerWindTurbine)`. One exception is `Polygon` which only have edge properties, so it will
use a `nodeType` filter `nodeType(power:Polygon)`.


#### Setting a manual filter

!!! warning annotate "Only for advanced users"
    Setting a manual filter is only recommended for advanced users. If you are not sure what you are doing, we recommend
    using the default filter set by **NEAT**.

You can set manuel filters by specifying the `filter` column in the view sheet. The syntax is as follows

* `hasData` - This will set a `hasData` filter with all the container mapped to by the view.
* `hasData(my_space:my_container)` - This will set a `hasData` filter with the specified container.
* `hasData(my_space:my_container, my_space:my_container2)` - This will set a `hasData` filter with the specified containers.
* `nodeType` - This will set a `nodeType` filter with the same node id as the view.
* `nodeType(my_space:my_node)` - This will set a `nodeType` filter with the specified node id.
* `nodeType(my_space:my_node, my_space:my_node2)` - This will set a `nodeType` filter with the specified node ids.
