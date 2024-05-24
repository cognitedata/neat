# Rules Excel Input

In the case, you have `Reference` and/or `Last` sheets in your Excel file, there are a few simplifications built
into **NEAT** to make it easier to enter the data model as well as make it clearer what is changed compared to the
`Reference` and `Last` objects.

## Exact Copying Classes or Views

If you want to have a class or view in the `user` `Rules` object that is in the `Reference` object or the `Last` object,
you do not have to copy over all the properties to your `Properties` sheet. You can just use the `Views` or `Classes`
sheet.

For example, given the following `View` sheet and given that the `metadata.space=power_analytic`
and `reference.metadata.space=power`:

| View                      | Implements    | ... | Reference                                      |
|---------------------------|---------------| --- | ---------------------------------------------- |
| Point                     | power:Point   |     |                                                |
| Polygon                   | power:Polygon |     |                                                |
| PowerForecast             |               |     |                                                |
| WeatherStation            |               |     |                                                |
| WindFarm                  |               |     |                                                |
| WindTurbine               |               |     |                                                |
| TimeseriesForecastProduct |               |     | power:TimeseriesForecastProduct(version=0.1.0) |

Then **NEAT** will create the views as follows:

* `Point` and `Polygon` are fully specified as these have the `Implements` column filled in, they will automatically
  inherit the properties from the `Point` and `Polygon` views in the `Reference` object.
* `TimeseriesForecastProduct` is referencing the `power:TimeseriesForecastProduct(version=0.1.0)` view in the `Reference`
  object, which means **NEAT** will add `power:TimeseriesForecastProduct(version=0.1.0)` to the `Implements` column
  automatically.
* `PowerForecast` and `WeatherStation` do not have any properties in the `Properties` sheet, so **NEAT** will assume
  the properties are the same as in the `LastProperties` sheet.
* The `WindFarm` and `WindTurbine` views have properties in the `Properties` sheet, how this is handled depends
  on the `metadata.extension` field, see [Adding Properties](#adding-properties).

## Adding Properties.

This is only relevant if `metadata.schema=extended`, which is used when you want to update a `Rules` object. Furthermore,
this also means that there must be a `LastProperties` sheet in the Excel file.

How **NEAT** interprets the properties in the `Properties` sheet depends on the `metadata.extension` field in the `View`.

### <code>metadata.extension=addition</code> - Combine Properties

The properties are added to the existing properties in the `LastProperties ` sheet. For example,
if you have the following `Properties` sheet and the classes `EnergyArea` and `GeneratingUnit` are
in the `LastProperties` sheet. Then, these properties will be **combined** to create the classes
`EnergyArea` and `GeneratingUnit`. Meaning the current version that is being build will have these
classes extended by two additional properties.

| Class                     | Property      | Value Type                | Min Count | Max Count  |
|---------------------------|---------------|---------------------------|-----------|------------|
| EnergyArea                | powerForecast | TimeseriesForecastProduct | 0         | 1          |
|                           |               |                           |           |            |
| GeneratingUnit            | powerForecast | TimeseriesForecastProduct | 0         | 1          |

### <code>metadata.extension=reshape/rebuild</code> - Replace Properties

The properties in the `Properties` sheet will replace the properties in the `LastProperties` sheet. For example,
if you have the following `Properties` sheet and the classes `EnergyArea` and `GeneratingUnit` are
in the `LastProperties` sheet. Then, these properties will **replace** the properties in the `LastProperties` sheet.
This means `EnergyArea` and `GeneratingUnit` will have completely new definition based only on the
properties defined in the `user` sheet.

| Class                     | Property      | Value Type                | Min Count | Max Count  |
|---------------------------|---------------|---------------------------|-----------|------------|
| EnergyArea                | powerForecast | TimeseriesForecastProduct | 0         | 1          |
| EnergyArea                | name          | string                    | 1         | 1          |
| EnergyArea                | geoLocation   | Polygon                   | 0         | 1          |
|                           |               |                           |           |            |
| GeneratingUnit            | powerForecast | TimeseriesForecastProduct | 0         | 1          |
| GeneratingUnit            | name          | string                    | 1         | 1          |
| GeneratingUnit            | type          | string                    | 0         | 1          |
