# View

## Filter
Filters are used to specify which nodes or edges should be returned when querying a view. We recommend having a
unique container for each view, and use the default filter set by the API.

## What is supported?
While **NEAT** physical data model are one-to-one with the CDF API specification for creating Data Models, the view filter is the
exception. If you compare to the [API specification for views](https://api-docs.cognite.com/20230101/tag/Views/operation/ApplyViews)
you will notice that `filter` is a very flexible parameter were you can specify an arbitrary complex filter.
**NEAT** has an opinionated approach to creating the view filter.

**NEAT** supports two filters

* `hasData` in `containers` - This filter returns all nodes/edges that have data in the specified containers.
* `NodeType` filter - This filter returns all nodes of a specific type. **NEAT** supports specifying multiple node types.

## Setting `hasData` and `nodeType` filters manually

!!! warning annotate "Only for advanced users"
    Setting a manual filter is only recommended for advanced users.

You can set manuel filters by specifying the `filter` column in the view sheet. The syntax is as follows

* `hasData` - This will set a `hasData` filter with all the container mapped to by the view.
* `hasData(my_space:my_container)` - This will set a `hasData` filter with the specified container.
* `hasData(my_space:my_container, my_space:my_container2)` - This will set a `hasData` filter with the specified containers.
* `nodeType` - This will set a `nodeType` filter with the same node id as the view.
* `nodeType(my_space:my_node)` - This will set a `nodeType` filter with the specified node id.
* `nodeType(my_space:my_node, my_space:my_node2)` - This will set a `nodeType` filter with the specified node ids.

## Setting a `rawFilter`

!!! warning annotate "Use it on your own risk!"

    The **NEAT** team is not responsible for any issues that may arise from setting a raw filter.
    This includes **NEAT** errors, **CDF** errors,  performance issues, etc. We do not recommend setting
    a raw filter unless you know what you are doing.

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

The exemplary data model spreadsheet with the above filters can be downloaded using [this link](../../artifacts/rules/dms-architect-rules-raw-filter-example.xlsx).
