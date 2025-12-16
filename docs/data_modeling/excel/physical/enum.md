# Enum

Enum (short for 'enumeration') is a text/string field that can only have a predefined set of values. You can
define an enumeration in the `enum` sheet in the physical data model spreadsheet, which you can then reference in the
`Value Type` column in the `properties` sheet.

## Defining an enumeration

To define an enumeration, you add one row for each value in the enumeration in the `enum` sheet. The example
below shows the enumeration for the `CoginteTimeseries.type` and `CogniteAnnotation.status` properties from
`CogniteCore` model.

| Collection               | Value     | Name      | Description                                         |
|--------------------------|-----------|-----------|-----------------------------------------------------|
| CogniteTimeseries.type   | numeric   | numeric   | Time series with double floating point data points. |
| CogniteTimeseries.type   | string    | string    | Time series with string data points.                |
| CogniteAnnotation.status | Approved  | Approved  |                                                     |
| CogniteAnnotation.status | Rejected  | Rejected  |                                                     |
| CogniteAnnotation.status | Suggested | Suggested |                                                     |

The `Collection` column is the unique identifier for the enumeration, in the example above, we have two
enumerations, `CogniteTimeseries.type` and `CogniteAnnotation.status`. The `Value` column contains the allowed
values for each enumeration. The `Name` and `Description` columns are optional and contain the display name
and description of the enumeration value.


## Referencing an enumeration

You can reference an enumeration in the `Value Type` column in the `properties` sheet. The syntax for referencing
an enumeration is `enum(collection=<CollectionName>)`. You can also specify an `unknownValue` parameter that will be
used when the value is unknown.

| View              | View Property | Value Type                                | Container         | Container Property |
|-------------------|---------------|-------------------------------------------|-------------------|--------------------|
| CogniteTimeSeries | type          | enum(collection=CogniteTimeSeries.type)   | CogniteTimeSeries | type               |
| CogniteAnnotation | status        | enum(collection=CogniteAnnotation.status) | CogniteAnnotation | status             |


