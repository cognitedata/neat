from typing import cast

import pytest

from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.importers._api_importer import DMSAPICreator
from cognite.neat._data_model.models.dms._references import ViewReference
from cognite.neat._exceptions import DataModelCreateException
from cognite.neat._issues import ConsistencyError, ModelSyntaxError
from tests.data import SNAPSHOT_CATALOG


@pytest.fixture(scope="session")
def snapshot() -> SchemaSnapshot:
    _, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario("cyclic_implements", "cdm", format="snapshots")
    return cdf_snapshot


class TestDataModelCreation:
    @pytest.mark.parametrize(
        "view_ref,errors",
        [
            pytest.param(
                "",
                [
                    ModelSyntaxError(message="No valid views provided to create the data model."),
                    ModelSyntaxError(message="Invalid view reference '': Could not parse entity."),
                ],
                id="empty string reference",
            ),
            pytest.param(
                "1983:CogniteAsset(version=1320)",
                [
                    ModelSyntaxError(message="No valid views provided to create the data model."),
                    ModelSyntaxError(
                        message=(
                            "Invalid view reference '1983:CogniteAsset(version=1320)', cannot parse it: "
                            "In field 'space', string '1983' does not match the required pattern: "
                            "'^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$'."
                        )
                    ),
                ],
                id="failed regex for space",
            ),
            pytest.param(
                "cdf=cdm:CogniteAsset(version=v1)",
                [
                    ModelSyntaxError(message="No valid views provided to create the data model."),
                    ModelSyntaxError(
                        message=(
                            "Invalid view reference 'cdf=cdm:CogniteAsset(version=v1)', cannot parse it: "
                            "Unexpected characters after properties at position 3. Got '='"
                        )
                    ),
                ],
                id="failed parsing",
            ),
            pytest.param(
                "cdf_cdm:CogniteAsset(ver=1320)",
                [
                    ModelSyntaxError(message="No valid views provided to create the data model."),
                    ModelSyntaxError(
                        message=("Invalid view reference 'cdf_cdm:CogniteAsset(ver=1320)': Missing 'version' property.")
                    ),
                ],
                id="missing version in options",
            ),
            pytest.param(
                "cdf_cdm:CogniteAsset(ver=1320),cdf_cdm:CogniteAsset(ver=1321)",
                [
                    ModelSyntaxError(message="No valid views provided to create the data model."),
                    ModelSyntaxError(
                        message=(
                            "Invalid view reference 'cdf_cdm:CogniteAsset(ver=1320),"
                            "cdf_cdm:CogniteAsset(ver=1321)': Expected a single view definition."
                        )
                    ),
                ],
                id="multiple references",
            ),
            pytest.param(
                "1983:CogniteAsset(version=1320)",
                [
                    ModelSyntaxError(message="No valid views provided to create the data model."),
                    ModelSyntaxError(
                        message=(
                            "Invalid view reference '1983:CogniteAsset(version=1320)', cannot parse it: "
                            "In field 'space', string '1983' does not match the required pattern: "
                            "'^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$'."
                        )
                    ),
                ],
                id="failed regex for space",
            ),
            pytest.param(
                "cdf_cdm:CogniteAsset(version=1320)",
                [
                    ConsistencyError(
                        message=(
                            "View 'cdf_cdm:CogniteAsset(version=1320)' not found in "
                            "the provided CDF snapshot. Cannot create data model."
                        )
                    )
                ],
                id="missing view in snapshot",
            ),
        ],
    )
    def test_various_errors(
        self, view_ref: str, errors: list[ModelSyntaxError | ConsistencyError], snapshot: SchemaSnapshot
    ) -> None:
        creator = DMSAPICreator(
            cdf_snapshot=snapshot,
            space="my_space",
            external_id="MySolution",
            version="v1",
            views=[
                view_ref,
            ],
        )

        with pytest.raises(DataModelCreateException) as exc_info:
            _ = creator.to_data_model()

        actual = exc_info.value.errors
        assert sorted(actual, key=lambda e: e.message) == sorted(errors, key=lambda e: e.message)

    @pytest.mark.parametrize(
        "views,connections",
        [
            pytest.param(
                ["cdf_cdm:CogniteAsset(version=v1)", "cdf_cdm:CogniteFile(version=v1)"],
                True,
                id="connection between new views established",
            ),
        ],
    )
    def test_successful_creation(self, views: list[str], connections: bool, snapshot: SchemaSnapshot) -> None:
        creator = DMSAPICreator(
            cdf_snapshot=snapshot, space="my_space", external_id="MySolution", version="myVer", views=views
        )

        data_model = creator.to_data_model()

        assert data_model.data_model.space == creator._space
        assert data_model.data_model.external_id == creator._external_id
        assert data_model.data_model.version == creator._version

        for view in data_model.views:
            assert view.space == creator._space
            assert view.version == creator._version

            for property_ in view.properties.values():
                if creator._resources.is_explicit_connection(property_):
                    assert property_.source is not None
                    assert property_.source in cast(list[ViewReference], data_model.data_model.views)
