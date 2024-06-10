from pathlib import Path

from cognite.client import data_modeling as dm
from rdflib import RDF
from rdflib.term import Literal

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.rules import importers
from cognite.neat.rules.models import InformationRules

_neat = DEFAULT_NAMESPACE
TRIPLES = tuple(
    [
        (_neat["Toyota"], RDF.type, _neat["Manufacturer"]),
        (_neat["Toyota"], _neat["name"], Literal("Toyota")),
        (_neat["Blue"], RDF.type, _neat["Color"]),
        (_neat["Blue"], _neat["name"], Literal("blue")),
        (_neat["Car1"], RDF.type, _neat["Car"]),
        (_neat["Car1"], _neat["make"], _neat["Toyota"]),
        (_neat["Car1"], _neat["year"], Literal("2020")),
        (_neat["Car1"], _neat["color"], _neat["Blue"]),
        (_neat["Ford"], RDF.type, _neat["Manufacturer"]),
        (_neat["Ford"], _neat["name"], Literal("Ford")),
        (_neat["Red"], RDF.type, _neat["Color"]),
        (_neat["Red"], _neat["name"], Literal("red")),
        (_neat["Car2"], RDF.type, _neat["Car"]),
        (_neat["Car2"], _neat["make"], _neat["Ford"]),
        (_neat["Car2"], _neat["year"], Literal("2018")),
        (_neat["Car2"], _neat["color"], _neat["Red"]),
    ]
)
MODEL_SPACE = "sp_example_car"
CONTAINERS = dm.ContainerApplyList(
    [
        dm.ContainerApply(
            space=MODEL_SPACE,
            external_id="Car",
            properties={
                "year": dm.ContainerProperty(dm.Int64()),
                "color": dm.ContainerProperty(dm.DirectRelation(is_list=False)),
            },
        ),
        dm.ContainerApply(
            space=MODEL_SPACE,
            external_id="Manufacturer",
            properties={"name": dm.ContainerProperty(dm.Text())},
        ),
        dm.ContainerApply(
            space=MODEL_SPACE,
            external_id="Color",
            properties={"name": dm.ContainerProperty(dm.Text())},
        ),
    ]
)

CAR_RULES: InformationRules = importers.ExcelImporter(
    Path(__file__).resolve().parent / "info-arch-car-rules.xlsx"
).to_rules()[0]

CAR_MODEL: dm.DataModel[dm.View] = dm.DataModel(
    space=MODEL_SPACE,
    external_id="CarModel",
    version="1",
    is_global=False,
    name=None,
    description=None,
    last_updated_time=1,
    created_time=1,
    views=[
        dm.View(
            space=MODEL_SPACE,
            external_id="Car",
            version="1",
            properties={
                "make": dm.MultiEdgeConnection(
                    source=dm.ViewId(MODEL_SPACE, "Manufacturer", "1"),
                    type=dm.DirectRelationReference(MODEL_SPACE, "Car.Manufacturer"),
                    name=None,
                    description=None,
                    edge_source=None,
                    direction="outwards",
                ),
                "year": dm.MappedProperty(
                    container=dm.ContainerId(MODEL_SPACE, "Car"),
                    container_property_identifier="year",
                    type=dm.Int64(),
                    nullable=False,
                    auto_increment=False,
                ),
                "color": dm.MappedProperty(
                    container=dm.ContainerId(MODEL_SPACE, "Car"),
                    container_property_identifier="color",
                    type=dm.DirectRelation(is_list=False),
                    nullable=False,
                    auto_increment=False,
                    source=dm.ViewId(MODEL_SPACE, "Color", "1"),
                ),
            },
            last_updated_time=0,
            created_time=0,
            description=None,
            name=None,
            filter=None,
            implements=None,
            writable=True,
            used_for="node",
            is_global=False,
        ),
        dm.View(
            space=MODEL_SPACE,
            external_id="Manufacturer",
            version="1",
            properties={
                "name": dm.MappedProperty(
                    container=dm.ContainerId(MODEL_SPACE, "Manufacturer"),
                    container_property_identifier="name",
                    type=dm.Text(),
                    nullable=False,
                    auto_increment=False,
                ),
            },
            last_updated_time=0,
            created_time=0,
            description=None,
            name=None,
            filter=None,
            implements=None,
            writable=True,
            used_for="node",
            is_global=False,
        ),
        dm.View(
            space=MODEL_SPACE,
            external_id="Color",
            version="1",
            properties={
                "name": dm.MappedProperty(
                    container=dm.ContainerId(MODEL_SPACE, "Color"),
                    container_property_identifier="name",
                    type=dm.Text(),
                    nullable=False,
                    auto_increment=False,
                ),
            },
            last_updated_time=0,
            created_time=0,
            description=None,
            name=None,
            filter=None,
            implements=None,
            writable=True,
            used_for="node",
            is_global=False,
        ),
    ],
)

NODE_TYPES = dm.NodeApplyList(
    [
        dm.NodeApply(MODEL_SPACE, "Car.Manufacturer"),
    ]
)

INSTANCE_SPACE = "sp_cars"
INSTANCES = [
    dm.NodeApply(
        space=INSTANCE_SPACE,
        external_id="Car1",
        sources=[
            dm.NodeOrEdgeData(
                source=CAR_MODEL.views[0].as_id(),
                properties={"year": 2020, "color": {"space": INSTANCE_SPACE, "externalId": "Blue"}},
            )
        ],
    ),
    dm.EdgeApply(
        space=INSTANCE_SPACE,
        external_id="Car1.make.Toyota",
        type=dm.DirectRelationReference(MODEL_SPACE, "Car.Manufacturer"),
        start_node=dm.DirectRelationReference(INSTANCE_SPACE, "Car1"),
        end_node=dm.DirectRelationReference(INSTANCE_SPACE, "Toyota"),
    ),
    dm.NodeApply(
        space=INSTANCE_SPACE,
        external_id="Car2",
        sources=[
            dm.NodeOrEdgeData(
                source=CAR_MODEL.views[0].as_id(),
                properties={"year": 2018, "color": {"space": INSTANCE_SPACE, "externalId": "Red"}},
            )
        ],
    ),
    dm.EdgeApply(
        space=INSTANCE_SPACE,
        external_id="Car2.make.Ford",
        type=dm.DirectRelationReference(MODEL_SPACE, "Car.Manufacturer"),
        start_node=dm.DirectRelationReference(INSTANCE_SPACE, "Car2"),
        end_node=dm.DirectRelationReference(INSTANCE_SPACE, "Ford"),
    ),
    dm.NodeApply(
        space=INSTANCE_SPACE,
        external_id="Ford",
        sources=[dm.NodeOrEdgeData(source=CAR_MODEL.views[1].as_id(), properties={"name": "Ford"})],
    ),
    dm.NodeApply(
        space=INSTANCE_SPACE,
        external_id="Toyota",
        sources=[dm.NodeOrEdgeData(source=CAR_MODEL.views[1].as_id(), properties={"name": "Toyota"})],
    ),
    dm.NodeApply(
        space=INSTANCE_SPACE,
        external_id="Blue",
        sources=[dm.NodeOrEdgeData(source=CAR_MODEL.views[2].as_id(), properties={"name": "blue"})],
    ),
    dm.NodeApply(
        space=INSTANCE_SPACE,
        external_id="Red",
        sources=[dm.NodeOrEdgeData(source=CAR_MODEL.views[2].as_id(), properties={"name": "red"})],
    ),
]
