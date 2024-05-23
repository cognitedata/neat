# DMS Rules Details

## Properties

### Connection
Connections are used to specify how nodes are connected. When implementing a connection, you have two options:

* Direct relation—This is cheap in terms of storage and query time.
* Edge connection—This is more flexible, but more expensive in terms of storage and query time.

To get more details on the difference between the two, see the
[see the data modeling documentation](https://docs.cognite.com/cdf/dm/dm_concepts/dm_spaces_instances#direct-relations-vs-edges).
Note that in addition to the mentioned differences, direct relations have an upper limit of 1000 relations per node.

#### How to set ValueType for a connection?

If the `connection` is set to `direct` or `edge` the ValueType must be a view. For example, in the for the `WindTurbine`
below the `blades` property is a direct relation to the `Blade` view.

| View          | ViewProperty       | Value Type | Relation  | IsList |
|---------------|------------------  |----------- |---------- |--------|
| WindTurbine   | blades             | Blade      | direct    | True   |

If the `connection` is set to `reverse` the ValueType must reference a View and the property in that view. For example,
in the `Blade` view below the `windTurbine` property is a reverse connection to the `WindTurbine` view.

| View  | ViewProperty | Value Type                   | Relation | IsList |
|-------|--------------|------------------------------|----------|--------|
| Blade | windTurbine  | WindTurbine(property=blades) | reverse  | False  |


#### How does NEAT implement the connection in CDF data modeling?

In **NEAT**, the type of connection is determined by the `connection` and `isList` columns in the properties sheet:

If `connection=direct`, then:

* `isList=true` - The connection is implemented as a list of direct relations.
* `isList=false` - The connection is implemented as a single direct relation.

If `connection=edge`, then:

* `isList=true` - The connection is implemented as `multi_edge_connection` with direction `outwards`.
* `isList=false` - The connection is implemented as `single_edge_connection` with direction `outwards`.

If `relation=reverse` the implementation depends on the relation of the other property.

If `otherProperty.connection=direct`, then:

* `isList=true` - The connection is implemented as `multi_reverse_direct_relation`.
* `isList=false` - The connection is implemented as `single_reverse_direct_relation`.

Otherwise, if the `otherProperty.connection=edge`, then:

* `isList=true` - The connection is implemented as `multi_edge_connection` with direction `inwards`.
* `isList=false` - The connection is implemented as `single_edge_connection` with direction `inwards`.

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


#### Setting `hasData` and `nodeType` filters manually

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

#### Setting a `rawFilter`

!!! warning annotate "Use it on your own risk!"
    The **NEAT** team is not responsible for any issues that may arise from setting a raw filter. This includes **NEAT** errors, **CDF** errors,  performance issues, etc. We do not recommend setting a raw filter unless you know what you are doing.

If the above filters are limiting and you have no other choice you can set a raw filter. The syntax is as follows:

* `rawFilter(your_custom_filter_as_json_string)` - This will set a raw filter with the specified filter.

In this example of the raw filter:

```
rawFilter({"equals": {"property": ["node", "type"], "value": {"space": "power", "externalId": "WindTurbine"}}})
```

the JSON string that defines filter is:

```JSON
{"equals": {"property": ["node", "type"], "value": {"space": "power", "externalId": "WindTurbine"}}}
```

BEWARE to properly form the JSON string, as it is easy to make mistakes. The JSON string must be a valid JSON object!

The exemplary `Rules` sheet with the above filters can be downloaded using [this link](../artifacts/rules/dms-architect-rules-raw-filter-example.xlsx).
