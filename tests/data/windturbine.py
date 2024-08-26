"""This is a DMS Model which contains edge with properties"""

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling.data_types import UnitReference

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

VIEWS = dm.ViewApplyList(
    [
        dm.ViewApply(
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
        ),
        dm.ViewApply(
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
        ),
        dm.ViewApply(
            space=_SPACE,
            external_id="Distance",
            version="v1",
            properties={
                "distance": dm.MappedPropertyApply(_DISTANCE_CONTAINER, "distance"),
            },
        ),
    ]
)

MODEL = dm.DataModelApply(
    space=_SPACE,
    external_id="WindTurbineModel",
    version="v1",
    views=VIEWS.as_ids(),
)
