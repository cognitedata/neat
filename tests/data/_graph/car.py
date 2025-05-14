from functools import lru_cache

from cognite.client import data_modeling as dm
from rdflib import RDF, Namespace
from rdflib.term import Literal

from cognite.neat.core._constants import DEFAULT_SPACE_URI
from cognite.neat.core._data_model import importers
from cognite.neat.core._data_model.importers._spreadsheet2data_model import (
    ExcelImporter,
)
from cognite.neat.core._data_model.models import ConceptualDataModel, PhysicalDataModel
from cognite.neat.core._data_model.models.physical import (
    UnverifiedPhysicalContainer,
    UnverifiedPhysicalDataModel,
    UnverifiedPhysicalMetadata,
    UnverifiedPhysicalProperty,
    UnverifiedPhysicalView,
)
from cognite.neat.core._data_model.transformers import VerifyConceptualDataModel

INSTANCE_SPACE = "sp_cars"
MODEL_SPACE = "sp_example_car"
_instance_ns = Namespace(DEFAULT_SPACE_URI.format(space=INSTANCE_SPACE))
_model_ns = Namespace(DEFAULT_SPACE_URI.format(space=MODEL_SPACE))
TRIPLES = tuple(
    [
        (_instance_ns["Toyota"], RDF.type, _model_ns["Manufacturer"]),
        (_instance_ns["Toyota"], _model_ns["name"], Literal("Toyota")),
        (_instance_ns["Blue"], RDF.type, _model_ns["Color"]),
        (_instance_ns["Blue"], _model_ns["name"], Literal("blue")),
        (_instance_ns["Car1"], RDF.type, _model_ns["Car"]),
        (_instance_ns["Car1"], _model_ns["Car.Manufacturer"], _instance_ns["Toyota"]),
        (_instance_ns["Car1"], _model_ns["year"], Literal(2020)),
        (_instance_ns["Car1"], _model_ns["color"], _instance_ns["Blue"]),
        (_instance_ns["Ford"], RDF.type, _model_ns["Manufacturer"]),
        (_instance_ns["Ford"], _model_ns["name"], Literal("Ford")),
        (_instance_ns["Red"], RDF.type, _model_ns["Color"]),
        (_instance_ns["Red"], _model_ns["name"], Literal("red")),
        (_instance_ns["Car2"], RDF.type, _model_ns["Car"]),
        (_instance_ns["Car2"], _model_ns["Car.Manufacturer"], _instance_ns["Ford"]),
        (_instance_ns["Car2"], _model_ns["year"], Literal(2018)),
        (_instance_ns["Car2"], _model_ns["color"], _instance_ns["Red"]),
    ]
)

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


@lru_cache(maxsize=1)
def get_care_rules() -> ConceptualDataModel:
    # To avoid circular import
    from tests.data import SchemaData

    read_rules = importers.ExcelImporter(SchemaData.Conceptual.info_arch_car_rules_xlsx).to_data_model()
    return VerifyConceptualDataModel().transform(read_rules)


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
                    immutable=False,
                ),
                "color": dm.MappedProperty(
                    container=dm.ContainerId(MODEL_SPACE, "Car"),
                    container_property_identifier="color",
                    type=dm.DirectRelation(is_list=False),
                    nullable=False,
                    auto_increment=False,
                    source=dm.ViewId(MODEL_SPACE, "Color", "1"),
                    immutable=False,
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
                    immutable=False,
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
                    immutable=False,
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

BASE_MODEL: PhysicalDataModel = UnverifiedPhysicalDataModel(
    metadata=UnverifiedPhysicalMetadata(
        space="sp_base",
        external_id="Base",
        version="1",
        creator="Anders",
    ),
    views=[UnverifiedPhysicalView(view="Entity")],
    containers=[UnverifiedPhysicalContainer(container="Entity")],
    properties=[
        UnverifiedPhysicalProperty(
            view="Entity",
            view_property="name",
            value_type="text",
            container="Entity",
            container_property="name",
        )
    ],
).as_verified_data_model()

NODE_TYPES = dm.NodeApplyList(
    [
        dm.NodeApply(MODEL_SPACE, "Car.Manufacturer"),
    ]
)

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
        type=dm.DirectRelationReference(MODEL_SPACE, "Car"),
    ),
    dm.EdgeApply(
        space=INSTANCE_SPACE,
        external_id="Car1.make.Toyota",
        start_node=dm.DirectRelationReference(INSTANCE_SPACE, "Car1"),
        type=dm.DirectRelationReference(MODEL_SPACE, "Car.Manufacturer"),
        end_node=dm.DirectRelationReference(INSTANCE_SPACE, "Toyota"),
    ),
    dm.NodeApply(
        space=INSTANCE_SPACE,
        external_id="Car2",
        sources=[
            dm.NodeOrEdgeData(
                source=CAR_MODEL.views[0].as_id(),
                properties={
                    "year": 2018,
                    "color": {"space": INSTANCE_SPACE, "externalId": "Red"},
                },
            )
        ],
        type=dm.DirectRelationReference(MODEL_SPACE, "Car"),
    ),
    dm.EdgeApply(
        space=INSTANCE_SPACE,
        external_id="Car2.make.Ford",
        start_node=dm.DirectRelationReference(INSTANCE_SPACE, "Car2"),
        type=dm.DirectRelationReference(MODEL_SPACE, "Car.Manufacturer"),
        end_node=dm.DirectRelationReference(INSTANCE_SPACE, "Ford"),
    ),
    dm.NodeApply(
        space=INSTANCE_SPACE,
        external_id="Ford",
        sources=[dm.NodeOrEdgeData(source=CAR_MODEL.views[1].as_id(), properties={"name": "Ford"})],
        type=dm.DirectRelationReference(MODEL_SPACE, "Manufacturer"),
    ),
    dm.NodeApply(
        space=INSTANCE_SPACE,
        external_id="Toyota",
        sources=[dm.NodeOrEdgeData(source=CAR_MODEL.views[1].as_id(), properties={"name": "Toyota"})],
        type=dm.DirectRelationReference(MODEL_SPACE, "Manufacturer"),
    ),
    dm.NodeApply(
        space=INSTANCE_SPACE,
        external_id="Blue",
        sources=[dm.NodeOrEdgeData(source=CAR_MODEL.views[2].as_id(), properties={"name": "blue"})],
        type=dm.DirectRelationReference(MODEL_SPACE, "Color"),
    ),
    dm.NodeApply(
        space=INSTANCE_SPACE,
        external_id="Red",
        sources=[dm.NodeOrEdgeData(source=CAR_MODEL.views[2].as_id(), properties={"name": "red"})],
        type=dm.DirectRelationReference(MODEL_SPACE, "Color"),
    ),
]


@lru_cache(maxsize=1)
def get_car_dms_rules() -> PhysicalDataModel:
    # Local import to avoid circular import
    from tests.data import SchemaData

    return (
        ExcelImporter(SchemaData.Physical.car_dms_rules_xlsx)
        .to_data_model()
        .unverified_data_model.as_verified_data_model()
    )
