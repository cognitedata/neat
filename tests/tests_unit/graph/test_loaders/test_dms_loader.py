import pytest
from cognite.client.data_classes import Asset, FileMetadata
from cognite.client.data_classes.data_modeling import InstanceApply

from cognite.neat import NeatSession
from cognite.neat._client.testing import monkeypatch_neat_client
from cognite.neat._constants import CLASSIC_CDF_NAMESPACE, DMS_DIRECT_RELATION_LIST_LIMIT
from cognite.neat._graph.extractors import AssetsExtractor, FilesExtractor, RdfFileExtractor
from cognite.neat._graph.loaders import DMSLoader
from cognite.neat._issues import IssueList
from cognite.neat._rules.catalog import imf_attributes
from cognite.neat._rules.importers import ExcelImporter, SubclassInferenceImporter
from cognite.neat._rules.models.entities._single_value import ClassEntity, ContainerEntity, ViewEntity
from cognite.neat._rules.transformers import InformationToDMS
from cognite.neat._store import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA, IMF_EXAMPLE


def test_metadata_as_json_filed():
    store = NeatGraphStore.from_memory_store()
    store.write(
        AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml", unpack_metadata=False, as_write=True)
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
    store.write(RdfFileExtractor(IMF_EXAMPLE))

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
    assert len(file_node.sources[0].properties["assetIds"]) == DMS_DIRECT_RELATION_LIST_LIMIT
