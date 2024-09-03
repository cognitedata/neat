# DMS Rules

## Properties

There are two types of properties in DMS Rules: `Connection` and `Data`. The `Connection` property is used to 
specify how nodes are connected, while the `Data` property is used to specify the data that is stored on the node.
These concepts matches a `Entity` and `Literal` in semantic modeling. It is recommended that you use `PascalCase` for
views, neat uses `camelCase` for data properties. This makes it easier to distinguish between the two by looking
at the `Value Type` column in the `Properties` sheet.

### Data Property
A data property is used to specify the data that is stored on the node. Below is an example of a data property:

| View        | View Property | Value Type                | Container      | Container Property |
|-------------|---------------|---------------------------|----------------|--------------------|
| WindTurbine | capacity      | float64(unit=power:megaw) | GeneratingUnit | capacity           |

This data property specifies that the `WindTurbine` view has a property called `capacity` that is a float64 with the unit
`power:megaw`. The data is stored in the `GeneratingUnit` container with the property `capacity`.

To see which value types are supported, see the 
[CDF API Spec for Container Creation](https://api-docs.cognite.com/20230101/tag/Containers/operation/ApplyContainers) section.
The `container.properties.type.type` field specifies the type of the property. 

<img src="../artifacts/figs/container_spec.png" height="200">

There are two `Value Type` that supports extra parameters

* `float32` and `float64` - These are used to specify floating-point numbers. The `unit` parameter is 
   used to specify the unit of the number. See [Units](units.md) for available units. See example above.
* `enum` - This is used to specify an enumeration. You need to set `collection` to the name of the enumeration and, 
   optionally, `unknownValue` to the value that should be used when the value is unknown. See example below. When
   enumerations are used, there is expected to be a corresponding `enum` sheet in the DMS Rules file with the 
   enumeration values.

| View        | View Property | Value Type                                      | Container   | Container Property |
|-------------|---------------|-------------------------------------------------|-------------|--------------------|
| WindTurbine | category      | enum(collection=category, unknownValue=onshore) | WindTurbine | category           |


### Connection Property

All connections have a `ValueType` that specifies the type of the connected node. For example:

| View          | ViewProperty       | Connection | Value Type  | Is List |
|---------------|------------------  |------------|-------------|---------|
| WindTurbine   | blades             | direct     | Blade       | True    |

This connection specifies that the `WindTurbine` view has a property called `blades` that is a direct relation to the `Blade` view.
In addition, the `Is List`, specifies that there can be multiple blades connected to a wind turbine.

#### Connection Implementation

The column `Connection` specifies how the connection is implemented in the CDF data model and can be one of the following:

* Direct relation—This is cheap in terms of storage and query time.
* Edge connection—This is more flexible, but more expensive in terms of storage and query time.
* Reverse connection—This is used to specify a connection from the other end of a direct relation or edge connection.

To get more details on the difference, see the [ data modeling documentation](https://docs.cognite.com/cdf/dm/dm_concepts/dm_spaces_instances#direct-relations-vs-edges).
Note that in addition to the mentioned differences, direct relations have an upper limit of 1000 connection per node.

The syntax for the `Connection` column is as follows:

* `direct` - This specifies a direct relation. There are no extra parameters. Note, however, that you need to 
   specify `Container` and `Container Property` as `direct` connections are stored in the container.
* `edge` - This specifies an edge connection. You can, optionally, specify `type`, `properties`,
   and `direction` as extra parameters.
* `reverse` - This specifies a reverse connection. You need to specify the `property` that the connection is
   reversing. 

**Edge example**:


| View        | ViewProperty | Connection                              | Value Type             | Is List |
|-------------|--------------|-----------------------------------------|------------------------|---------|
| WindTurbine | metmasts     | edge(type=distance,properties=Distance) | MetMast                | True    |
| Distance    | distance     |                                         | float64(unit=length:m) | False   |

This connection specifies that the `WindTurbine` view has a property called `metmasts` that is an edge connection 
to the `MetMast` view. The edges are of type `distance` and have properties stored in the `Distance` view. The
`Distance` view has a property called `distance` that is a float64 with the unit `length:m`.

Why is both `type` and `properties` needed? The `type` specifies the type of the edge, this is used for filtering
when querying the data model. The `properties` specifies the properties that are stored on the edge. This is used
to store data on the edge. In the example above, we can, for example, write a query that returns all MetMast
(Wheather Station) that are connected to a WindTurbine with a distance less than 100 meters.

**Reverse example**:

| View       | ViewProperty   | Connection                 | Value Type   | Is List |
|------------|----------------|----------------------------|--------------|---------|
| MetMast    | windTurbines   | reverse(property=metmasts) | WindTurbine  | True    |

This connection specifies that the `MetMast` view has a property called `windTurbines` that is a reverse connection
of the `metmasts` property in the `WindTurbine` view. The `Is List` specifies that there can be multiple wind turbines
connected to a MetMast. 

Connecting this example to the previous example, we see that the reverse here will be an edge that is pointing the 
opposite direction of the `WindTurbine`.`metmasts` edge. The reverse enable use to easily reuse the same edge
for both directions.

**Caveat**: The `reverse` connection of a `direct` connection that has `Is List=True` is not supported by CDF.

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
  the default filter is `nodeType` filter with all node ids matching the id of the view in the enterprise data model.
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
