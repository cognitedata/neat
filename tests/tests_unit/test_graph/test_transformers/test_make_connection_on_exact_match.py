import contextlib
import io

from cognite.client.data_classes import Asset, FileMetadata

from cognite.neat import NeatSession
from cognite.neat.v0.core._constants import CLASSIC_CDF_NAMESPACE
from cognite.neat.v0.core._instances.extractors._classic_cdf._assets import AssetsExtractor
from cognite.neat.v0.core._instances.extractors._classic_cdf._files import FilesExtractor


def test_exact_match() -> None:
    neat = NeatSession()
    manufacturer = Asset(id=1, external_id="manufacturer", name="manufacturer1")
    file = FileMetadata(id=1, external_id="file", source="manufacturer1", name="datasheet")
    neat._state.instances.store.write(AssetsExtractor([manufacturer], as_write=True, namespace=CLASSIC_CDF_NAMESPACE))
    neat._state.instances.store.write(FilesExtractor([file], as_write=True, namespace=CLASSIC_CDF_NAMESPACE))

    # Neat Session does not raise an error, but prints it.
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        neat.prepare.instances.make_connection_on_exact_match(
            ("Asset", "name"), ("File", "source"), connection="files", limit=None
        )
    printed_statements = output.getvalue()
    assert not printed_statements.startswith("[ERROR]"), (
        f"Failed to make connection on exact match: {printed_statements}"
    )

    has_property = neat._state.instances.store.queries.select.type_with_property(
        CLASSIC_CDF_NAMESPACE["Asset"], CLASSIC_CDF_NAMESPACE["files"]
    )
    assert has_property is True
