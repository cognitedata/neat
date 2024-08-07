from dataclasses import dataclass


@dataclass
class UnitEntry:
    semantic_type: str
    unit_type: str
    unit: str


_UNIT_ENTRIES = [
    UnitEntry("Acceleration", "AccelerationUnit", "centimetrePerSecondSquared"),
    UnitEntry("Acceleration", "AccelerationUnit", "gForce"),
    UnitEntry("Acceleration", "AccelerationUnit", "metrePerSecondSquared"),
    UnitEntry("Angle", "AngleUnit", "degreeOfArc"),
    UnitEntry("Angle", "AngleUnit", "minuteOfArc"),
    UnitEntry("Angle", "AngleUnit", "radian"),
    UnitEntry("Angle", "AngleUnit", "secondOfArc"),
    UnitEntry("Angle", "AngleUnit", "turn"),
    UnitEntry("AngularAcceleration", "AngularAccelerationUnit", "radianPerSecondSquared"),
    UnitEntry("AngularVelocity", "AngularVelocityUnit", "degreePerSecond"),
    UnitEntry("AngularVelocity", "AngularVelocityUnit", "radianPerSecond"),
    UnitEntry("AngularVelocity", "AngularVelocityUnit", "revolutionPerMinute"),
    UnitEntry("AngularVelocity", "AngularVelocityUnit", "revolutionPerSecond"),
    UnitEntry("Area", "AreaUnit", "acre"),
    UnitEntry("Area", "AreaUnit", "hectare"),
    UnitEntry("Area", "AreaUnit", "squareCentimetre"),
    UnitEntry("Area", "AreaUnit", "squareFoot"),
    UnitEntry("Area", "AreaUnit", "squareInch"),
    UnitEntry("Area", "AreaUnit", "squareKilometre"),
    UnitEntry("Area", "AreaUnit", "squareMetre"),
    UnitEntry("Area", "AreaUnit", "squareMillimetre"),
    UnitEntry("Capacitance", "CapacitanceUnit", "farad"),
    UnitEntry("Capacitance", "CapacitanceUnit", "microfarad"),
    UnitEntry("Capacitance", "CapacitanceUnit", "millifarad"),
    UnitEntry("Capacitance", "CapacitanceUnit", "nanofarad"),
    UnitEntry("Capacitance", "CapacitanceUnit", "picofarad"),
    UnitEntry("Current", "CurrentUnit", "ampere"),
    UnitEntry("Current", "CurrentUnit", "microampere"),
    UnitEntry("Current", "CurrentUnit", "milliampere"),
    UnitEntry("DataRate", "DataRateUnit", "bitPerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "bytePerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "exbibitPerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "exbibytePerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "gibibitPerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "gibibytePerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "kibibitPerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "kibibytePerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "mebibitPerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "mebibytePerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "tebibitPerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "tebibytePerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "yobibitPerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "yobibytePerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "zebibitPerSecond"),
    UnitEntry("DataRate", "DataRateUnit", "zebibytePerSecond"),
    UnitEntry("DataSize", "DataSizeUnit", "bit"),
    UnitEntry("DataSize", "DataSizeUnit", "byte"),
    UnitEntry("DataSize", "DataSizeUnit", "exbibit"),
    UnitEntry("DataSize", "DataSizeUnit", "exbibyte"),
    UnitEntry("DataSize", "DataSizeUnit", "gibibit"),
    UnitEntry("DataSize", "DataSizeUnit", "gibibyte"),
    UnitEntry("DataSize", "DataSizeUnit", "kibibit"),
    UnitEntry("DataSize", "DataSizeUnit", "kibibyte"),
    UnitEntry("DataSize", "DataSizeUnit", "mebibit"),
    UnitEntry("DataSize", "DataSizeUnit", "mebibyte"),
    UnitEntry("DataSize", "DataSizeUnit", "tebibit"),
    UnitEntry("DataSize", "DataSizeUnit", "tebibyte"),
    UnitEntry("DataSize", "DataSizeUnit", "yobibit"),
    UnitEntry("DataSize", "DataSizeUnit", "yobibyte"),
    UnitEntry("DataSize", "DataSizeUnit", "zebibit"),
    UnitEntry("DataSize", "DataSizeUnit", "zebibyte"),
    UnitEntry("Density", "DensityUnit", "gramPerCubicMetre"),
    UnitEntry("Density", "DensityUnit", "kilogramPerCubicMetre"),
    UnitEntry("Distance", "LengthUnit", "astronomicalUnit"),
    UnitEntry("Distance", "LengthUnit", "centimetre"),
    UnitEntry("Distance", "LengthUnit", "foot"),
    UnitEntry("Distance", "LengthUnit", "inch"),
    UnitEntry("Distance", "LengthUnit", "kilometre"),
    UnitEntry("Distance", "LengthUnit", "metre"),
    UnitEntry("Distance", "LengthUnit", "micrometre"),
    UnitEntry("Distance", "LengthUnit", "mile"),
    UnitEntry("Distance", "LengthUnit", "millimetre"),
    UnitEntry("Distance", "LengthUnit", "nanometre"),
    UnitEntry("Distance", "LengthUnit", "nauticalMile"),
    UnitEntry("ElectricCharge", "ChargeUnit", "coulomb"),
    UnitEntry("Energy", "EnergyUnit", "electronvolt"),
    UnitEntry("Energy", "EnergyUnit", "gigajoule"),
    UnitEntry("Energy", "EnergyUnit", "joule"),
    UnitEntry("Energy", "EnergyUnit", "kilojoule"),
    UnitEntry("Energy", "EnergyUnit", "kilowattHour"),
    UnitEntry("Energy", "EnergyUnit", "megaelectronvolt"),
    UnitEntry("Energy", "EnergyUnit", "megajoule"),
    UnitEntry("Force", "ForceUnit", "newton"),
    UnitEntry("Force", "ForceUnit", "ounce"),
    UnitEntry("Force", "ForceUnit", "pound"),
    UnitEntry("Force", "ForceUnit", "ton"),
    UnitEntry("Frequency", "FrequencyUnit", "gigahertz"),
    UnitEntry("Frequency", "FrequencyUnit", "hertz"),
    UnitEntry("Frequency", "FrequencyUnit", "kilohertz"),
    UnitEntry("Frequency", "FrequencyUnit", "megahertz"),
    UnitEntry("Humidity", "DensityUnit", "gramPerCubicMetre"),
    UnitEntry("Humidity", "DensityUnit", "kilogramPerCubicMetre"),
    UnitEntry("Illuminance", "IlluminanceUnit", "footcandle"),
    UnitEntry("Illuminance", "IlluminanceUnit", "lux"),
    UnitEntry("Inductance", "InductanceUnit", "henry"),
    UnitEntry("Inductance", "InductanceUnit", "microhenry"),
    UnitEntry("Inductance", "InductanceUnit", "millihenry"),
    UnitEntry("Latitude", "AngleUnit", "degreeOfArc"),
    UnitEntry("Latitude", "AngleUnit", "minuteOfArc"),
    UnitEntry("Latitude", "AngleUnit", "radian"),
    UnitEntry("Latitude", "AngleUnit", "secondOfArc"),
    UnitEntry("Latitude", "AngleUnit", "turn"),
    UnitEntry("Length", "LengthUnit", "astronomicalUnit"),
    UnitEntry("Length", "LengthUnit", "centimetre"),
    UnitEntry("Length", "LengthUnit", "foot"),
    UnitEntry("Length", "LengthUnit", "inch"),
    UnitEntry("Length", "LengthUnit", "kilometre"),
    UnitEntry("Length", "LengthUnit", "metre"),
    UnitEntry("Length", "LengthUnit", "micrometre"),
    UnitEntry("Length", "LengthUnit", "mile"),
    UnitEntry("Length", "LengthUnit", "millimetre"),
    UnitEntry("Length", "LengthUnit", "nanometre"),
    UnitEntry("Length", "LengthUnit", "nauticalMile"),
    UnitEntry("Longitude", "AngleUnit", "degreeOfArc"),
    UnitEntry("Longitude", "AngleUnit", "minuteOfArc"),
    UnitEntry("Longitude", "AngleUnit", "radian"),
    UnitEntry("Longitude", "AngleUnit", "secondOfArc"),
    UnitEntry("Longitude", "AngleUnit", "turn"),
    UnitEntry("Luminance", "LuminanceUnit", "candelaPerSquareMetre"),
    UnitEntry("Luminosity", "PowerUnit", "gigawatt"),
    UnitEntry("Luminosity", "PowerUnit", "horsepower"),
    UnitEntry("Luminosity", "PowerUnit", "kilowatt"),
    UnitEntry("Luminosity", "PowerUnit", "kilowattHourPerYear"),
    UnitEntry("Luminosity", "PowerUnit", "megawatt"),
    UnitEntry("Luminosity", "PowerUnit", "microwatt"),
    UnitEntry("Luminosity", "PowerUnit", "milliwatt"),
    UnitEntry("Luminosity", "PowerUnit", "watt"),
    UnitEntry("LuminousFlux", "LuminousFluxUnit", "lumen"),
    UnitEntry("LuminousIntensity", "LuminousIntensityUnit", "candela"),
    UnitEntry("MagneticFlux", "MagneticFluxUnit", "maxwell"),
    UnitEntry("MagneticFlux", "MagneticFluxUnit", "weber"),
    UnitEntry("MagneticInduction", "MagneticInductionUnit", "tesla"),
    UnitEntry("Mass", "MassUnit", "gram"),
    UnitEntry("Mass", "MassUnit", "kilogram"),
    UnitEntry("Mass", "MassUnit", "microgram"),
    UnitEntry("Mass", "MassUnit", "milligram"),
    UnitEntry("Mass", "MassUnit", "slug"),
    UnitEntry("Mass", "MassUnit", "tonne"),
    UnitEntry("MassFlowRate", "MassFlowRateUnit", "gramPerHour"),
    UnitEntry("MassFlowRate", "MassFlowRateUnit", "gramPerSecond"),
    UnitEntry("MassFlowRate", "MassFlowRateUnit", "kilogramPerHour"),
    UnitEntry("MassFlowRate", "MassFlowRateUnit", "kilogramPerSecond"),
    UnitEntry("Power", "PowerUnit", "gigawatt"),
    UnitEntry("Power", "PowerUnit", "horsepower"),
    UnitEntry("Power", "PowerUnit", "kilowatt"),
    UnitEntry("Power", "PowerUnit", "kilowattHour"),
    UnitEntry("Power", "PowerUnit", "megawatt"),
    UnitEntry("Power", "PowerUnit", "microwatt"),
    UnitEntry("Power", "PowerUnit", "milliwatt"),
    UnitEntry("Power", "PowerUnit", "watt"),
    UnitEntry("Pressure", "PressureUnit", "bar"),
    UnitEntry("Pressure", "PressureUnit", "inchesOfMercury"),
    UnitEntry("Pressure", "PressureUnit", "inchesOfWater"),
    UnitEntry("Pressure", "PressureUnit", "kilopascal"),
    UnitEntry("Pressure", "PressureUnit", "millibar"),
    UnitEntry("Pressure", "PressureUnit", "millimetresOfMercury"),
    UnitEntry("Pressure", "PressureUnit", "pascal"),
    UnitEntry("Pressure", "PressureUnit", "poundPerSquareInch"),
    UnitEntry("RelativeHumidity", "Unitless", "percent"),
    UnitEntry("RelativeHumidity", "Unitless", "unity"),
    UnitEntry("Resistance", "ResistanceUnit", "kiloohm"),
    UnitEntry("Resistance", "ResistanceUnit", "megaohm"),
    UnitEntry("Resistance", "ResistanceUnit", "milliohm"),
    UnitEntry("Resistance", "ResistanceUnit", "ohm"),
    UnitEntry("SoundPressure", "SoundPressureUnit", "bel"),
    UnitEntry("SoundPressure", "SoundPressureUnit", "decibel"),
    UnitEntry("Temperature", "TemperatureUnit", "degreeCelsius"),
    UnitEntry("Temperature", "TemperatureUnit", "degreeFahrenheit"),
    UnitEntry("Temperature", "TemperatureUnit", "kelvin"),
    UnitEntry("Thrust", "ForceUnit", "newton"),
    UnitEntry("Thrust", "ForceUnit", "ounce"),
    UnitEntry("Thrust", "ForceUnit", "pound"),
    UnitEntry("Thrust", "ForceUnit", "ton"),
    UnitEntry("TimeSpan", "TimeUnit", "day"),
    UnitEntry("TimeSpan", "TimeUnit", "hour"),
    UnitEntry("TimeSpan", "TimeUnit", "microsecond"),
    UnitEntry("TimeSpan", "TimeUnit", "millisecond"),
    UnitEntry("TimeSpan", "TimeUnit", "minute"),
    UnitEntry("TimeSpan", "TimeUnit", "nanosecond"),
    UnitEntry("TimeSpan", "TimeUnit", "second"),
    UnitEntry("TimeSpan", "TimeUnit", "year"),
    UnitEntry("Torque", "TorqueUnit", "newtonMetre"),
    UnitEntry("Velocity", "VelocityUnit", "centimetrePerSecond"),
    UnitEntry("Velocity", "VelocityUnit", "kilometrePerHour"),
    UnitEntry("Velocity", "VelocityUnit", "kilometrePerSecond"),
    UnitEntry("Velocity", "VelocityUnit", "knot"),
    UnitEntry("Velocity", "VelocityUnit", "metrePerHour"),
    UnitEntry("Velocity", "VelocityUnit", "metrePerSecond"),
    UnitEntry("Velocity", "VelocityUnit", "milePerHour"),
    UnitEntry("Velocity", "VelocityUnit", "milePerSecond"),
    UnitEntry("Voltage", "VoltageUnit", "kilovolt"),
    UnitEntry("Voltage", "VoltageUnit", "megavolt"),
    UnitEntry("Voltage", "VoltageUnit", "microvolt"),
    UnitEntry("Voltage", "VoltageUnit", "millivolt"),
    UnitEntry("Voltage", "VoltageUnit", "volt"),
    UnitEntry("Volume", "VolumeUnit", "cubicCentimetre"),
    UnitEntry("Volume", "VolumeUnit", "cubicFoot"),
    UnitEntry("Volume", "VolumeUnit", "cubicInch"),
    UnitEntry("Volume", "VolumeUnit", "cubicMetre"),
    UnitEntry("Volume", "VolumeUnit", "fluidOunce"),
    UnitEntry("Volume", "VolumeUnit", "gallon"),
    UnitEntry("Volume", "VolumeUnit", "litre"),
    UnitEntry("Volume", "VolumeUnit", "millilitre"),
    UnitEntry("VolumeFlowRate", "VolumeFlowRateUnit", "litrePerHour"),
    UnitEntry("VolumeFlowRate", "VolumeFlowRateUnit", "litrePerSecond"),
    UnitEntry("VolumeFlowRate", "VolumeFlowRateUnit", "millilitrePerHour"),
    UnitEntry("VolumeFlowRate", "VolumeFlowRateUnit", "millilitrePerSecond"),
]

UNIT_TYPE_BY_SEMANTIC_TYPE = {entry.semantic_type: entry.unit_type for entry in _UNIT_ENTRIES}
# This is a bit dangerous, as unit names are not unique across types
# It is only used as a backup in the parsing of units.
ENTRY_BY_UNIT = {entry.unit: entry for entry in _UNIT_ENTRIES}
