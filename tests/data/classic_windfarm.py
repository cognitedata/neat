from cognite.client.data_classes import (
    Asset,
    DataSet,
    Event,
    FileMetadata,
    Label,
    LabelDefinition,
    Relationship,
    Sequence,
    SequenceColumn,
    TimeSeries,
)

ds_source = DataSet(
    external_id="source_ds",
    name="Source DS",
    description="Source data set",
    metadata={
        "some": "extra",
        "information": "here",
    },
    write_protected=True,
    id=123,
    created_time=1,
    last_updated_time=2,
)
ds_analysis = DataSet(
    external_id="usecase_01",
    name="Usecase 01",
    description="Usecase 01 data set",
    metadata={
        "some": "other",
        "information": "here",
    },
    write_protected=False,
    id=124,
    created_time=3,
    last_updated_time=4,
)
ds_maintenance = DataSet(
    external_id="maintenance",
    name="Maintenance",
    description="Maintenance data set",
    metadata={
        "some": "other",
        "information": "here",
    },
    write_protected=True,
    id=125,
    created_time=5,
    last_updated_time=6,
)


root = Asset(
    external_id="Utsira",
    name="Utsira",
    description="Utsira wind farm",
    data_set_id=ds_source.id,
    metadata={"blob": "data"},
    source="manufacturer1",
    labels=[Label("PowerGeneratingUnit")],
    id=4,
    created_time=5,
    last_updated_time=6,
)

wind_turbine = Asset(
    external_id="WT-01",
    name="WT-01",
    description="Wind turbine 01",
    data_set_id=ds_source.id,
    metadata={"blob": "data"},
    source="manufacturer1",
    labels=[Label("WindTurbine"), Label("PowerGeneratingUnit")],
    parent_id=root.id,
    parent_external_id=root.external_id,
    id=5,
    created_time=7,
    last_updated_time=8,
)

wind_turbine2 = Asset(
    external_id="WT-02",
    name="WT-02",
    description="Wind turbine 02",
    data_set_id=ds_source.id,
    metadata={"blob": "data"},
    source="manufacturer1",
    labels=[Label("WindTurbine"), Label("PowerGeneratingUnit")],
    parent_id=root.id,
    parent_external_id=root.external_id,
    id=6,
    created_time=9,
    last_updated_time=10,
)

measurment_root = Asset(
    external_id="Measurement",
    name="Measurement",
    description="Measurement",
    data_set_id=ds_source.id,
    metadata={"blob": "data"},
    source="manufacturer2",
    labels=[Label("Measurement")],
    id=7,
    created_time=11,
    last_updated_time=12,
)

metmast = Asset(
    external_id="MetMast",
    name="MetMast",
    description="Meteorological mast",
    data_set_id=ds_source.id,
    metadata={"blob": "data"},
    source="manufacturer2",
    labels=[Label("metMast"), Label("Measurement")],
    parent_id=measurment_root.id,
    parent_external_id=measurment_root.external_id,
    id=6,
    created_time=9,
    last_updated_time=10,
)

turbine_to_metmast = Relationship(
    external_id="WT-01_to_MetMast",
    source_external_id=wind_turbine.external_id,
    source_type="Asset",
    target_external_id=metmast.external_id,
    target_type="Asset",
    data_set_id=ds_source.id,
    labels=[Label("metMast")],
    confidence=1.0,
)

turbine_to_metmast2 = Relationship(
    external_id="WT-02_to_MetMast",
    source_external_id=wind_turbine2.external_id,
    source_type="Asset",
    target_external_id=metmast.external_id,
    target_type="Asset",
    data_set_id=ds_source.id,
    labels=[Label("metMast")],
    confidence=1.0,
)

power_curve = Sequence(
    id=1,
    name="Power curve Manufacturer 1",
    external_id="power_curve_manufacturer1",
    metadata={"blob": "data"},
    description="Power curve from manufacturer 1",
    columns=[
        SequenceColumn(
            external_id="wind_speed",
            name="Wind speed",
            description="Wind speed",
            metadata={"blob": "data"},
            value_type="Double",
        ),
        SequenceColumn(
            external_id="power",
            name="Power",
            description="Power",
            metadata={"blob": "data"},
            value_type="Double",
        ),
    ],
)

label_definitions = [
    LabelDefinition(
        external_id="PowerGeneratingUnit",
        name="Power generating unit",
        description="Power generating unit",
        data_set_id=ds_source.id,
    ),
    LabelDefinition(
        external_id="WindTurbine",
        name="Wind turbine",
        description="Wind turbine",
        data_set_id=ds_source.id,
    ),
    LabelDefinition(
        external_id="metMast",
        name="Meteorological mast",
        description="Meteorological mast",
        data_set_id=ds_source.id,
    ),
    LabelDefinition(
        external_id="Measurement",
        name="Measurement",
        description="Measurement",
        data_set_id=ds_source.id,
    ),
]

wind_turbine_production = TimeSeries(
    external_id="WT-01_production",
    name="WT-01 production",
    description="WT-01 production",
    metadata={"blob": "data"},
    data_set_id=ds_source.id,
    asset_id=wind_turbine.id,
    is_step=False,
    is_string=False,
    unit_external_id="power:megaw",
    created_time=1,
    last_updated_time=2,
)

wind_turbine_production2 = TimeSeries(
    external_id="WT-02_production",
    name="WT-02 production",
    description="WT-02 production",
    metadata={"blob": "data"},
    data_set_id=ds_source.id,
    asset_id=wind_turbine2.id,
    is_step=False,
    is_string=False,
    unit_external_id="power:megaw",
    created_time=3,
    last_updated_time=4,
)

wind_turbine_forecast = TimeSeries(
    external_id="WT-01_forecast",
    name="WT-01 forecast",
    description="WT-01 forecast",
    metadata={"blob": "data"},
    data_set_id=ds_analysis.id,
    asset_id=wind_turbine.id,
    is_step=False,
    is_string=False,
    unit_external_id="power:megaw",
    created_time=5,
    last_updated_time=6,
)

wind_turbine_forecast2 = TimeSeries(
    external_id="WT-02_forecast",
    name="WT-02 forecast",
    description="WT-02 forecast",
    metadata={"blob": "data"},
    data_set_id=ds_analysis.id,
    asset_id=wind_turbine2.id,
    is_step=False,
    is_string=False,
    unit_external_id="power:megaw",
    created_time=7,
    last_updated_time=8,
)

maintenance = Event(
    external_id="planned:WT-01:2022-01-01",
    description="Planned maintenance",
    data_set_id=ds_maintenance.id,
    start_time=400,
    end_time=500,
    type="Maintenance",
    subtype="Planned",
    asset_ids=[wind_turbine.id],
    source="manufacturer1",
    metadata={"blob": "data"},
    id=12345,
    created_time=1,
    last_updated_time=2,
)

data_sheet = FileMetadata(
    external_id="WT-01_datasheet",
    name="WT-01 datasheet",
    source="manufacturer1",
    asset_ids=[wind_turbine.id],
    data_set_id=ds_source.id,
    metadata={"blob": "data"},
    id=12345,
    created_time=1,
    last_updated_time=2,
)
