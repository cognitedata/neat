import numpy as np
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
    SequenceColumnList,
    SequenceRow,
    SequenceRows,
    TimeSeries,
)

from cognite.neat._client.data_classes.neat_sequence import NeatSequence
from cognite.neat._constants import CLASSIC_CDF_NAMESPACE
from cognite.neat._graph.extractors import (
    AssetsExtractor,
    DataSetExtractor,
    EventsExtractor,
    FilesExtractor,
    LabelsExtractor,
    RelationshipsExtractor,
    SequencesExtractor,
    TimeSeriesExtractor,
)
from cognite.neat._graph.extractors._classic_cdf._base import ClassicCDFBaseExtractor

# This is a knowledge graph built on top of the classic CDF resources. It is used to test the CDFClassicGraphImporter.

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

DATASETS = [ds_source, ds_analysis, ds_maintenance]


root = Asset(
    external_id="Utsira",
    name="Utsira",
    description="Utsira wind farm",
    data_set_id=ds_source.id,
    metadata={"assetCategory": "WindFarm"},
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
    metadata={"assetCategory": "Turbine", "turbineType": "V112/3075", "maxCapacity": "3"},
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
    metadata={"assetCategory": "Turbine", "turbineType": "V112/3075", "maxCapacity": "3"},
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
    metadata={"assetCategory": "root"},
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
    metadata={"assetCategory": "MetMast", "height": "100"},
    source="manufacturer2",
    labels=[Label("metMast"), Label("Measurement")],
    parent_id=measurment_root.id,
    parent_external_id=measurment_root.external_id,
    id=8,
    created_time=9,
    last_updated_time=10,
)

ASSETS = [root, wind_turbine, wind_turbine2, measurment_root, metmast]

turbine_to_metmast = Relationship(
    external_id="WT-01_to_MetMast",
    source_external_id=wind_turbine.external_id,
    source_type="Asset",
    target_external_id=metmast.external_id,
    target_type="Asset",
    data_set_id=ds_source.id,
    labels=[Label("metMast")],
)

turbine_to_metmast2 = Relationship(
    external_id="WT-02_to_MetMast",
    source_external_id=wind_turbine2.external_id,
    source_type="Asset",
    target_external_id=metmast.external_id,
    target_type="Asset",
    data_set_id=ds_source.id,
    labels=[Label("metMast")],
)

RELATIONSHIPS = [turbine_to_metmast, turbine_to_metmast2]

SEQUENCE_COLUMNS = SequenceColumnList(
    [
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
    ]
)

power_curve = Sequence(
    id=1,
    name="Power curve Manufacturer 1",
    external_id="power_curve_manufacturer1",
    metadata={"blob": "data", "turbineType": "V112/3075"},
    description="Power curve from manufacturer 1",
    asset_id=wind_turbine.id,
    columns=SEQUENCE_COLUMNS,
    created_time=1,
    last_updated_time=2,
    data_set_id=ds_source.id,
)

SEQUENCES = [power_curve]

_WIND_SPEEDS = np.arange(0, 25.5, 0.5).tolist()
_RAW_POWER = """0	0	0	0	0	0	7000	53000	123000		208000	309000		427000	567000		732000
927000	1149000	1401000		1688000		2006000	2348000	2693000		3011000	3252000		3388000	3436000	3448000	3450000
3450000	3450000	3450000	3450000	3450000	3450000	3450000	3450000	3450000	3450000	3450000	3450000	3450000	3450000	3450000
3450000	3450000	3450000	3450000	3450000	3450000	3450000	3450000	3450000"""
_POWER = list(map(float, _RAW_POWER.replace("\n", " ").split()))

SEQUENCE_ROWS = SequenceRows(
    rows=[
        SequenceRow(
            row_number=row_no,
            values=[speed, power],
        )
        for row_no, (speed, power) in enumerate(zip(_WIND_SPEEDS, _POWER, strict=False))
    ],
    columns=SEQUENCE_COLUMNS,
    id=1,
    external_id="power_curve_manufacturer1",
)

NEAT_SEQUENCES = [NeatSequence.from_cognite_sequence(power_curve, SEQUENCE_ROWS.rows)]

LABELS = [
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
    id=1,
    external_id="WT-01_production",
    name="WT-01 production",
    description="WT-01 production",
    metadata={"timeSeriesCategory": "Production"},
    data_set_id=ds_source.id,
    asset_id=wind_turbine.id,
    is_step=False,
    is_string=False,
    unit_external_id="power:megaw",
    created_time=1,
    last_updated_time=2,
)

wind_turbine_production2 = TimeSeries(
    id=2,
    external_id="WT-02_production",
    name="WT-02 production",
    description="WT-02 production",
    metadata={"timeSeriesCategory": "Production"},
    data_set_id=ds_source.id,
    asset_id=wind_turbine2.id,
    is_step=False,
    is_string=False,
    unit_external_id="power:megaw",
    created_time=3,
    last_updated_time=4,
)

wind_turbine_forecast = TimeSeries(
    id=3,
    external_id="WT-01_forecast",
    name="WT-01 forecast",
    description="WT-01 forecast",
    metadata={"timeSeriesCategory": "Forecast"},
    data_set_id=ds_analysis.id,
    asset_id=wind_turbine.id,
    is_step=False,
    is_string=False,
    unit_external_id="power:megaw",
    created_time=5,
    last_updated_time=6,
)

wind_turbine_forecast2 = TimeSeries(
    id=4,
    external_id="WT-02_forecast",
    name="WT-02 forecast",
    description="WT-02 forecast",
    metadata={"timeSeriesCategory": "Forecast"},
    data_set_id=ds_analysis.id,
    asset_id=wind_turbine2.id,
    is_step=False,
    is_string=False,
    unit_external_id="power:megaw",
    created_time=7,
    last_updated_time=8,
)

TIME_SERIES = [
    wind_turbine_production,
    wind_turbine_production2,
    wind_turbine_forecast,
    wind_turbine_forecast2,
]

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
    metadata={"eventCategory": "Maintenance"},
    id=1,
    created_time=1,
    last_updated_time=2,
)

EVENTS = [maintenance]

data_sheet = FileMetadata(
    external_id="WT-01_datasheet",
    name="WT-01_datasheet.txt",
    source="manufacturer1",
    asset_ids=[wind_turbine.id],
    data_set_id=ds_source.id,
    metadata={"fileCategory": "DataSheet"},
    id=2,
    created_time=1,
    last_updated_time=2,
)

FILES = [data_sheet]


def create_extractors() -> list[ClassicCDFBaseExtractor]:
    args = dict(namespace=CLASSIC_CDF_NAMESPACE, unpack_metadata=False, as_write=True)
    return [
        DataSetExtractor(DATASETS, **args),
        AssetsExtractor(ASSETS, **args),
        RelationshipsExtractor(RELATIONSHIPS, **args),
        TimeSeriesExtractor(TIME_SERIES, **args),
        SequencesExtractor(NEAT_SEQUENCES, **args),
        FilesExtractor(FILES, **args),
        LabelsExtractor(LABELS, **args),
        EventsExtractor(EVENTS, **args),
    ]
