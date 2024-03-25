# Analytic Solution Data Model

!!! warning annotate "Warning"

    This tutorial is work in progress and is not yet completed.


This tutorial demonstrates how to build a solution model for an analytic use case. We assume that there is already
an enterprise model developed, as in the [Knowledge Acquisition](./part-1-knowledge-acquisition.md) tutorial, which
will be used as the basis for the solution model.

## Introduction

Olav is a data scientist at `Acme Corporation`. He is responsible for building forecasting models for the wind farm
to predict the power output of the wind turbines. These forecasts are used by the trading department to sell
the power on the market.

## Selecting from the Enterprise Model
The most important part of Olav's new solution model is the `WindTurbine` and the `WindFarm` concepts. First,
let's look at the `WindTurbine` from the enterprise model.

| Class       | Property             | Value Type |
|-------------|----------------------|------------|
| WindTurbine | name                 | string     |
| WindTurbine | type                 | string     |
| WindTurbine | geoLocation          | Point      |
| WindTurbine | manufacturer         | string     |
| WindTurbine | lifeExpectancy       | integer    |
| WindTurbine | ratedPower           | float      |
| WindTurbine | hubHeight            | float      |
| WindTurbine | actualPower          | timeseries |
| WindTurbine | arrayCableConnection | ArrayCable |

The most important properties for Olav's forecasting model are the `actualPower` and the `ratedPower`. In addition,
he needs the `geoLocation` to calculate the wind speed and the `hubHeight` to adjust the wind speed to the height
of the wind turbine. In addition, there might be differences in the power output between the wind turbines based
on the manufacturer, life expectancy, and the type of wind turbine. However, Olav decides that
arrayCableConnection is not important for his forecasting model, so the `WindTurbine`in the solution model will
not have this property.

Next, let's look at the `WindFarm` from the enterprise model.

| Class       | Property             | Value Type         |
|-------------|----------------------|--------------------|
| WindFarm    | name                 | string             |
| WindFarm    | geoLocation          | Polygon            |
| WindFarm    | ratedPower           | float              |
| WindFarm    | activePower          | timeseries         |
| WindFarm    | substation           | OffshoreSubstation |
| WindFarm    | exportCable          | ExportCable        |
| WindFarm    | arrayCable           | ArrayCable         |
| WindFarm    | windTurbines         | WindTurbine        |

Olav decides that this can be simplified for his forecasting model down to `name`, `geoLocation` and `windTurbines`.
The `ratedPower` and `activePower` are not needed as it is the sum for all the `WindTurbines`. The
`substation`, `exportCable`, and `arrayCable` are not needed for the forecasting model.

Based on the choices above, Olav will also include `Point` and `Polygon` from the enterprise model as they are needed
for the `geoLocation` of the `WindTurbine` and `WindFarm`.

## Adding new Concepts

To make good forecasts, Olav needs historical and forecasted weather data. Thus, he will have to extend the solution
model with new concepts for the weather data. In addition, he needs to add a concept for the forecasted power output
of the wind turbines.

Olav chose to model the weather data as a `WeatherStation`. The `WeatherStation` concept will look
as follows:

| Class            | Property              | Value Type   |
|------------------|-----------------------|--------------|
| WeatherStation  | name                  | string       |
| WeatherStation  | type                  | string       |
| WeatherStation  | source                | string       |
| WeatherStation  | geoLocation           | Point        |
| WeatherStation  | windSpeed             | timeseries   |
| WeatherStation  | windFromDirection     | timeseries   |
| WeatherStation  | airTemperature        | timeseries   |
| WeatherStation  | airPressureAtSeaLevel | timeseries   |
| WeatherStation  | relativeHumidity      | timeseries   |
| WeatherStation  | cloudAreaFraction     | timeseries   |

The advantage of this concept is that it can be used both for historical weather data and forecasted weather data.

The weather observations will be connected to the `WindFarm`:

| Class        | Property            | Value Type      | Min Count | Max Count |
|--------------|---------------------|-----------------|-----------|-----------|
| WindFarm     | name                | string          | 1         | 1         |
| ...          | ...                 | ...             | ...       | ...       |
| WindFarm     | weatherForecasts    | WeatherStation | 0         | Inf       |
| WindFarm     | weatherObservations | WeatherStation | 0         | Inf       |

The `weatherForecasts` will be used for the forecasted weather data, and the `weatherObservations` will be used for
the historical weather data.

The forecasted power output of the wind turbines will be modeled as a `ForecastedPowerOutput`:

| Class                   | Property           | Value Type | Min Count | Max Count |
|-------------------------|--------------------|------------|-----------|-----------|
| ForecastedPowerOutput   | name               | string     | 1         | 1         |
| ForecastedPowerOutput   | algorithm          | string     | 1         | 1         |
| ForecastedPowerOutput   | inputTimeseries    | timeseries | 1         | Inf       |
| ForecastedPowerOutput   | forecastParameters | json       | 0         | 1         |
| ForecastedPowerOutput   | forecast           | timeseries | 1         | 1         |

The `inputTimeseries` will be the input to the forecasting model, and the `forecast` will be the output of the
forecasting model. The `forecastParameters` will be used to store the parameters used in the forecasting model.

Olav decides to store the forecasted power output for each wind turbine in the `WindFarm`:

| Class         | Property            | Value Type            | Min Count | Max Count |
|---------------|---------------------|-----------------------|-----------|-----------|
| WindFarm      | name                | string                | 1         | 1         |
| ...           | ...                 | ...                   | ...       | ...       |
| WindFarm      | powerForecasts      | ForecastedPowerOutput | 0         | Inf       |
| WindFarm      | minPowerForecast    | timeseries            | 0         | 1         |
| WindFarm      | mediumPowerForecast | timeseries            | 0         | 1         |
| WindFarm      | maxPowerForecast    | timeseries            | 0         | 1         |

The `powerForecasts` will be used to store the forecasted power output for each wind turbine. In addition, Olav
adds `minPowerForecast`, `mediumPowerForecast`, and `maxPowerForecast` to store the minimum, medium, and maximum
forecasted power output for the wind farm. The `powerForecasts` property Olav will only be used in the
solution data model, while the `min`, `medium`, and `max` properties will be added back to the enterprise model such
that they can be consumed by other users. See the [Extending the Enterprise Model](./part-3-extending-enterprise-model.md)
tutorial for more information.

In addition, Olav adds `lowPowerForecast`, `highPowerForecast`, and `expectedPowerForecast` to the `WindFarm`:

| Class         | Property              | Value Type | Min Count | Max Count |
|---------------|-----------------------|------------|-----------|-----------|
| WindFarm      | name                  | string     | 1         | 1         |
| ...           | ...                   | ...        | ...       | ...       |
| WindFarm      | lowPowerForecast      | timeseries | 0         | 1         |
| WindFarm      | highPowerForecast     | timeseries | 0         | 1         |
| WindFarm      | expectedPowerForecast | timeseries | 0         | 1         |

Similar to the `min`, `medium`, and `max` properties, the `low`, `high`, and `expected` properties will be added
back to the enterprise model.


## Implementing the Solution Model

Olav has now defined the solution model for the forecasting use case. The next step is to implement the solution model.
**NEAT** gives him a good out of the box suggestion for how to implement the solution model, but to ensure that the
model is well implemented Olav asks the DMS solution architect, Alice, to validate the model.

Alice asks Olav a few questions on how he is planning to use the new `ForecastedPowerOutput` and `WeatherStation`
concepts. Based on Olav's answers, Alice suggests that the `name` and `algorithm` in the `ForecastedPowerOutput` should
be indexed to ensure that the queries are fast. Also for the `WeatherStation`, Alice suggests that the `name`,
`type`, and `source` should be indexed to ensure that the queries are fast.

## Download Olav's Solution Model

TODO

## Summary

**Analytic Task**

1. Select from the enterprise model
2. Add new concepts

**Analytic Expert usage of **NEAT**:

1. Select from the enterprise model
2. Validate the model
3. Add new concepts
4. Deploy the model
