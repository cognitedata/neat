import pytest
from cognite.client.data_classes import Asset, FileMetadata
from cognite.client.data_classes.data_modeling import InstanceApply
from rdflib import RDF, Literal

from cognite.neat import NeatSession
from cognite.neat.core._client.testing import monkeypatch_neat_client
from cognite.neat.core._constants import (
    CLASSIC_CDF_NAMESPACE,
    DEFAULT_NAMESPACE,
    DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT,
)
from cognite.neat.core._graph.extractors import (
    AssetsExtractor,
    FilesExtractor,
    RdfFileExtractor,
)
from cognite.neat.core._graph.loaders import DMSLoader
from cognite.neat.core._issues import IssueList, NeatIssue
from cognite.neat.core._issues.warnings import PropertyDirectRelationLimitWarning
from cognite.neat.core._rules.catalog import imf_attributes
from cognite.neat.core._rules.importers import ExcelImporter, SubclassInferenceImporter
from cognite.neat.core._rules.models.dms import (
    DMSInputContainer,
    DMSInputMetadata,
    DMSInputProperty,
    DMSInputRules,
    DMSInputView,
)
from cognite.neat.core._rules.models.entities._single_value import (
    ClassEntity,
    ContainerEntity,
    ViewEntity,
)
from cognite.neat.core._rules.transformers import DMSToInformation, InformationToDMS
from cognite.neat.core._shared import Triple
from cognite.neat.core._store import NeatGraphStore
from tests.data import GraphData, InstanceData


def test_metadata_as_json_filed():
    store = NeatGraphStore.from_memory_store()
    store.write(
        AssetsExtractor.from_file(InstanceData.AssetCentricCDF.assets_yaml, unpack_metadata=False, as_write=True)
    )

    importer = SubclassInferenceImporter(IssueList(), store.dataset, data_model_id=("neat_space", "MyAsset", "1"))

    info_rules = importer.to_rules().rules.as_verified_rules()
    # Need to change externalId as it is not allowed in DMS
    for prop in info_rules.properties:
        if prop.property_ == "externalId":
            prop.property_ = "classicExternalId"

    dms_rules = InformationToDMS().transform(info_rules)

    # simulating update of the DMS rules
    dms_rules.views[0].view = ViewEntity.load("neat_space:MyAsset(version=inferred)")

    for prop in dms_rules.properties:
        prop.view = ViewEntity.load("neat_space:MyAsset(version=inferred)")
        prop.view_property = f"my_{prop.view_property}"

    # simulating update of the INFORMATION rules

    info_rules.classes[0].class_ = ClassEntity.load("neat_space:YourAsset")
    for prop in info_rules.properties:
        prop.class_ = ClassEntity.load("neat_space:YourAsset")
        prop.property_ = f"your_{prop.property_}"

    loader = DMSLoader(dms_rules, info_rules, store, dms_rules.metadata.space)
    instances = {instance.external_id: instance for instance in loader._load() if isinstance(instance, InstanceApply)}

    # metadata not unpacked but kept as Json obj
    assert isinstance(
        instances["Asset_4288662884680989"].sources[0].properties["my_metadata"],
        dict,
    )

    assert instances["Asset_4288662884680989"].type.external_id == "MyAsset"
    assert instances["Asset_4288662884680989"].type.space == "neat_space"


def test_imf_attribute_nodes():
    # this test also accounts for renaming of classes
    # as well omitting to remove namespace from values if
    # properties are not specified to be object properties

    info_rules = ExcelImporter(imf_attributes).to_rules().rules.as_verified_rules()

    dms_rules = InformationToDMS().transform(info_rules)

    store = NeatGraphStore.from_oxi_local_store()
    store.write(RdfFileExtractor(GraphData.imf_temp_transmitter_complete_ttl))

    loader = DMSLoader(dms_rules, info_rules, store, instance_space="knowledge")
    knowledge_nodes = list(loader.load())

    assert len(knowledge_nodes) == 56

    assert knowledge_nodes[0].sources[0].properties["predicate"] == "CFIHOS-40000524"
    assert len(store.multi_type_instances[store.default_named_graph]) == 63


@pytest.mark.xfail(reason="Need to update the prefix to work on verified rules")
def test_extract_above_direct_relation_limit() -> None:
    with monkeypatch_neat_client() as client:
        neat = NeatSession(client, storage="oxigraph")
        assets = [Asset(id=i, name=f"Asset_{i}") for i in range(1, 1001)]
        file = FileMetadata(id=1, name="P&ID file", asset_ids=list(range(1, 1001)))

        neat._state.instances.store.write(AssetsExtractor(assets, namespace=CLASSIC_CDF_NAMESPACE, as_write=True))
        neat._state.instances.store.write(FilesExtractor([file], namespace=CLASSIC_CDF_NAMESPACE, as_write=True))

        neat.infer()
        neat.prepare.data_model.prefix("Classic")
        neat.convert()
        dms_rules = neat._state.rule_store.last_verified_dms_rules
        # Default conversion uses edges for connections. We need to change it to direct relations
        asset_ids = next(prop for prop in dms_rules.properties if prop.view_property == "assetIds")
        asset_ids.connection = "direct"
        asset_ids.container_property = "assetIds"
        asset_ids.container = ContainerEntity.load("neat_space:ClassicFile")

        schema = dms_rules.as_schema()

        client.iam.verify_capabilities.return_value = []
        client.data_modeling.views.retrieve.return_value = schema.views.values()
        client.data_modeling.containers.retrieve.return_value = schema.containers.values()
        neat.to.cdf.instances()

    # Twice for the asset due to the self-relation, parentId
    # and once for the file
    assert client.data_modeling.instances.apply.call_count == 3
    file_node = client.data_modeling.instances.apply.call_args_list[2].args[0][0]
    assert file_node.sources[0].source.external_id == "ClassicFile"
    assert len(file_node.sources[0].properties["assetIds"]) == DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT


def test_dms_load_respect_container_cardinality() -> None:
    dms = DMSInputRules(
        metadata=DMSInputMetadata(
            space="sp_schema_space",
            external_id="MyModel",
            creator="doctrino",
            version="v1",
        ),
        properties=[
            # Adding two connections to ensure the correct limit is used for each of them.
            DMSInputProperty(
                "MyView",
                "toOther2",
                "MyOtherView",
                connection="direct",
                max_count=2,
                container="MyContainer",
                container_property="toOther2",
            ),
            DMSInputProperty(
                "MyView",
                "toOther3",
                "MyOtherView",
                connection="direct",
                max_count=3,
                container="MyContainer",
                container_property="toOther3",
            ),
            DMSInputProperty(
                "MyOtherView", "name", "text", max_count=1, container="MyOtherContainer", container_property="name"
            ),
        ],
        views=[
            DMSInputView("MyView"),
            DMSInputView("MyOtherView"),
        ],
        containers=[
            DMSInputContainer("MyContainer"),
            DMSInputContainer("MyOtherContainer"),
        ],
    ).as_verified_rules()
    info = DMSToInformation().transform(dms)
    info.metadata.physical = dms.metadata.identifier
    dms.sync_with_info_rules(info)

    store = NeatGraphStore.from_memory_store()
    namespace = DEFAULT_NAMESPACE
    my_type = namespace["MyView"]
    my_other_type = namespace["MyOtherView"]
    to_other_prop2 = namespace["toOther2"]
    to_other_prop3 = namespace["toOther3"]
    name_prop = namespace["name"]
    my_instance_external_id = "MyInstance"
    my_instance_uri = namespace[my_instance_external_id]
    triples: list[Triple] = [(my_instance_uri, RDF.type, my_type)]
    other_count = 4
    for i in range(other_count):
        id_ = namespace[f"OtherInstance{i}"]
        triples.append((id_, RDF.type, my_other_type))
        triples.append((id_, name_prop, Literal(f"Name{i}")))
        # Connections, these should be limited by the max_count
        triples.append((my_instance_uri, to_other_prop2, id_))
        triples.append((my_instance_uri, to_other_prop3, id_))

    for triple in triples:
        store.dataset.add(triple)

    # Link the schema to the triples
    info.classes[0].instance_source = my_type
    info.classes[1].instance_source = my_other_type
    info.properties[0].instance_source = [to_other_prop2]
    info.properties[1].instance_source = [to_other_prop3]
    info.properties[2].instance_source = [name_prop]

    loader = DMSLoader(
        dms,
        info,
        store,
        instance_space="sp_instance_space",
    )
    results = list(loader.load(stop_on_exception=True))

    assert len(results) == other_count + 1 + 2

    node_by_external_id = {node.external_id: node for node in results if isinstance(node, InstanceApply)}
    assert set(node_by_external_id) == {f"OtherInstance{i}" for i in range(other_count)} | {my_instance_external_id}
    my_instance = node_by_external_id[my_instance_external_id]
    assert len(my_instance.sources) == 1
    source = my_instance.sources[0]
    assert set(source.properties.keys()) == {"toOther2", "toOther3"}
    assert len(source.properties["toOther2"]) == 2
    assert len(source.properties["toOther3"]) == 3

    issues = [issue for issue in results if isinstance(issue, NeatIssue)]
    assert len(issues) == 2
    unexpected_issues = [issue for issue in issues if not isinstance(issue, PropertyDirectRelationLimitWarning)]
    assert not unexpected_issues
