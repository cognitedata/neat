import pytest

from cognite.neat._data_model._analysis import ResourceSource, ValidationResources
from cognite.neat._data_model.models.dms import ViewReference, ViewRequest
from tests.data.snapshots.catalog import Catalog


@pytest.fixture(scope="module")
def scenarios() -> dict[str, ValidationResources]:
    catalog = Catalog()
    scenarios = {
        "bi-directional-with-cdm": catalog.load_scenario(
            "bi_directional_connections",
            cdf_scenario_name="cdm",
            modus_operandi="additive",
            include_cdm=True,
            format="validation-resource",
        )
    }
    return scenarios


class TestValidationResources:
    @pytest.mark.parametrize(
        "scenario,view_ref,property_,source,expected",
        [
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="not-existent", external_id="DoesNotExist", version="v1"),
                None,
                "auto",
                None,
                id="view not found",
            ),
        ],
    )
    def test_select_view(
        self,
        scenario: str,
        view_ref: ViewReference,
        property_: str | None,
        source: ResourceSource,
        expected: ViewRequest | None,
        scenarios: dict,
    ) -> None:
        resources = scenarios[scenario]
        view_request = resources.select_view(
            view_ref=view_ref,
            property_=property_,
            source=source,
        )
        assert view_request == expected
