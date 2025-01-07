from cognite.client.data_classes import Asset

from cognite.neat import NeatSession
from cognite.neat._constants import CLASSIC_CDF_NAMESPACE
from cognite.neat._graph.extractors._classic_cdf._assets import AssetsExtractor
from tests.data import classic_windfarm


def test_exact_match() -> None:
    neat = NeatSession()
    manufacturer = Asset(
        external_id="manufacturer",
        # Matching FileMetadata.source
        name="manufacturer1",
        description="Manufacturer of the wind turbine",
    )
    # Load test data
    for extractor in classic_windfarm.create_extractors():
        neat._state.instances.store.write(extractor)
    neat._state.instances.store.write(AssetsExtractor([manufacturer], as_write=True, namespace=CLASSIC_CDF_NAMESPACE))

    neat.prepare.instances.make_connection_on_exact_match(
        ("Asset", "name"), ("FileMetadata", "source"), connection="files", limit=None
    )

    has_property = neat._state.instances.store.queries.type_with_property(
        CLASSIC_CDF_NAMESPACE["Asset"], CLASSIC_CDF_NAMESPACE["name"]
    )
    assert has_property is True
