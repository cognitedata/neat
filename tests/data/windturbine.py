"""This is a DMS Model which contains edge with properties"""

import datetime
from typing import Any

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import NodeApply
from cognite.client.data_classes.data_modeling.data_types import UnitReference

from cognite.neat.rules.models.dms import (
    DMSInputContainer,
    DMSInputMetadata,
    DMSInputNodeType,
    DMSInputProperty,
    DMSInputRules,
    DMSInputView,
    DMSSchema,
)
from cognite.neat.utils.cdf.data_classes import ContainerApplyDict, NodeApplyDict, SpaceApplyDict, ViewApplyDict

_SPACE = "sp_windturbine"

CONTAINERS = dm.ContainerApplyList(
    [
        dm.ContainerApply(
            space=_SPACE,
            external_id="WindTurbine",
            used_for="node",
            properties={
                "name": dm.ContainerProperty(dm.Text()),
                "capacity": dm.ContainerProperty(dm.Float64(unit=UnitReference("power:megaw"))),
            },
        ),
        dm.ContainerApply(
            space=_SPACE,
            external_id="MetMast",
            used_for="node",
            properties={
                "name": dm.ContainerProperty(dm.Text()),
                "windSpeed": dm.ContainerProperty(dm.TimeSeriesReference()),
            },
        ),
        dm.ContainerApply(
            space=_SPACE,
            external_id="Distance",
            used_for="edge",
            properties={
                "distance": dm.ContainerProperty(dm.Float64(unit=UnitReference("length:m"))),
            },
        ),
    ]
)
_WINDTURBINE_CONTAINER = CONTAINERS[0].as_id()
_METMAST_CONTAINER = CONTAINERS[1].as_id()
_DISTANCE_CONTAINER = CONTAINERS[2].as_id()

WIND_TURBINE = dm.ViewApply(
    space=_SPACE,
    external_id="WindTurbine",
    version="v1",
    properties={
        "name": dm.MappedPropertyApply(_WINDTURBINE_CONTAINER, "name"),
        "capacity": dm.MappedPropertyApply(_WINDTURBINE_CONTAINER, "capacity"),
        "metmasts": dm.MultiEdgeConnectionApply(
            type=dm.DirectRelationReference(_SPACE, "distance"),
            source=dm.ViewId(_SPACE, "MetMast", "v1"),
            edge_source=dm.ViewId(_SPACE, "Distance", "v1"),
            direction="outwards",
        ),
    },
)

METMAST = dm.ViewApply(
    space=_SPACE,
    external_id="MetMast",
    version="v1",
    properties={
        "name": dm.MappedPropertyApply(_METMAST_CONTAINER, "name"),
        "windSpeed": dm.MappedPropertyApply(_METMAST_CONTAINER, "windSpeed"),
        "windTurbines": dm.MultiEdgeConnectionApply(
            type=dm.DirectRelationReference(_SPACE, "distance"),
            source=dm.ViewId(_SPACE, "WindTurbine", "v1"),
            edge_source=dm.ViewId(_SPACE, "Distance", "v1"),
            direction="inwards",
        ),
    },
)
DISTANCE = dm.ViewApply(
    space=_SPACE,
    external_id="Distance",
    version="v1",
    properties={
        "distance": dm.MappedPropertyApply(_DISTANCE_CONTAINER, "distance"),
    },
)

VIEWS = dm.ViewApplyList(
    [
        WIND_TURBINE,
        METMAST,
        DISTANCE,
    ]
)

MODEL = dm.DataModelApply(
    space=_SPACE,
    external_id="WindTurbineModel",
    version="v1",
    views=VIEWS.as_ids(),
)
NODE_TYPE = NodeApply(space=_SPACE, external_id="distance")
SCHEMA = DMSSchema(
    data_model=MODEL,
    spaces=SpaceApplyDict.from_iterable([dm.SpaceApply(space=_SPACE)]),
    containers=ContainerApplyDict.from_iterable(CONTAINERS),
    views=ViewApplyDict.from_iterable(VIEWS),
    node_types=NodeApplyDict([NODE_TYPE]),
)

_TODAY = datetime.datetime.now()

_DEFAULTS: dict[str, Any] = dict(immutable=False, nullable=True, is_list=False)


INPUT_RULES = DMSInputRules(
    metadata=DMSInputMetadata(
        "complete",
        _SPACE,
        "WindTurbineModel",
        "MISSING",
        "v1",
        data_model_type="enterprise",
        updated=_TODAY,
        created=_TODAY,
    ),
    properties=[
        DMSInputProperty(
            "WindTurbine", "name", "text", container="WindTurbine", container_property="name", **_DEFAULTS
        ),
        DMSInputProperty(
            "WindTurbine",
            "capacity",
            "float64(unit=power:megaw)",
            container="WindTurbine",
            container_property="capacity",
            **_DEFAULTS,
        ),
        DMSInputProperty(
            "WindTurbine", "metmasts", "MetMast", connection="edge(properties=Distance, type=distance)", is_list=True
        ),
        DMSInputProperty("MetMast", "name", "text", container="MetMast", container_property="name", **_DEFAULTS),
        DMSInputProperty(
            "MetMast", "windSpeed", "timeseries", container="MetMast", container_property="windSpeed", **_DEFAULTS
        ),
        DMSInputProperty(
            "MetMast",
            "windTurbines",
            "WindTurbine",
            connection="reverse(property=metmasts)",
            is_list=True,
        ),
        DMSInputProperty(
            "Distance",
            "distance",
            "float64(unit=length:m)",
            container="Distance",
            container_property="distance",
            **_DEFAULTS,
        ),
    ],
    views=[DMSInputView("WindTurbine"), DMSInputView("MetMast"), DMSInputView("Distance")],
    containers=[
        DMSInputContainer("WindTurbine", used_for="node"),
        DMSInputContainer("MetMast", used_for="node"),
        DMSInputContainer("Distance", used_for="edge"),
    ],
    node_types=[DMSInputNodeType("distance")],
)

if __name__ == "__main__":
    from pathlib import Path

    from cognite.neat.rules.exporters import ExcelExporter
    from cognite.neat.rules.importers import DMSImporter
    from cognite.neat.rules.transformers import ImporterPipeline

    ROOT = Path(__file__).resolve().parent.parent.parent / "playground"

    dms_rules = ImporterPipeline.verify(DMSImporter(SCHEMA, metadata=INPUT_RULES.metadata))

    ExcelExporter().export_to_file(dms_rules, ROOT / "windturbine.xlsx")
