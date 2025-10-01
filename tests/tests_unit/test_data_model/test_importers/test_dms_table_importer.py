from collections.abc import Iterable

import pytest

from cognite.neat._data_model.importers import DMSTableImporter
from cognite.neat._data_model.models.dms import (
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DataModelRequest,
    RequestSchema,
    SpaceRequest,
    TextProperty,
    ViewCorePropertyRequest,
    ViewReference,
    ViewRequest,
)
from cognite.neat._utils.useful_types import CellValue


def test_valid_dms_table_format() -> Iterable[tuple]:
    yield pytest.param(
        {
            "Metadata": {
                "space": "cdf_cdm",
                "externalId": "CogniteCore",
                "version": "v1",
                "name": "Cognite Core Data Model",
                "description": "The Cognite Core Data Model (CDM) is a standardized data model for industrial data.",
            },
            "Properties": [
                {
                    "View": "CogniteDescribable",
                    "View Property": "name",
                    "Name": None,
                    "Description": None,
                    "Connection": None,
                    "Value Type": "text",
                    "Min Count": 0,
                    "Max Count": 1,
                    "Immutable": False,
                    "Default": None,
                    "Container": "CogniteDescribable",
                    "Container Property": "name",
                    "Index": "btree:name(cursorable=False)",
                    "Constraint": None,
                }
            ],
            "Views": [
                {
                    "View": "CogniteDescribable",
                    "Name": "Cognite Describable",
                    "Description": "The describable core concept is used as a standard way of "
                    "holding the bare minimum of information about the instance",
                    "Implements": None,
                    "Filter": True,
                }
            ],
            "Containers": [
                {
                    "Container": "CogniteDescribable",
                    "Name": None,
                    "Description": None,
                    "Constraint": None,
                    "Used For": "all",
                }
            ],
        },
        RequestSchema.from_lists(
            data_model=DataModelRequest(
                space="cdf_cdm",
                externalId="CogniteCore",
                version="v1",
                name="Cognite Core Data Model",
                description="The Cognite Core Data Model (CDM) is a standardized data model for industrial data.",
                views=[ViewReference(space="cdf_cdm", externalId="CogniteDescribable", version="v1")],
            ),
            spaces=[
                SpaceRequest(
                    space="cdf_cdm",
                    name="Cognite Core Data Model",
                    description="The Cognite Core Data Model (CDM) is a standardized data model for industrial data.",
                )
            ],
            views=[
                ViewRequest(
                    space="cdf_cdm",
                    externalId="CogniteDescribable",
                    version="v1",
                    name="Cognite Describable",
                    description="The describable core concept is used as a standard way of holding the bare minimum "
                    "of information about the instance",
                    implements=None,
                    properties={
                        "name": ViewCorePropertyRequest(
                            name=None,
                            description=None,
                            container=ContainerReference(space="cdf_cdm", externalId="CogniteDescribable"),
                            containerPropertyIdentifier="name",
                        ),
                    },
                )
            ],
            containers=[
                ContainerRequest(
                    space="cdf_cdm",
                    externalId="CogniteDescribable",
                    usedFor="all",
                    properties={
                        "name": ContainerPropertyDefinition(
                            immutable=False,
                            nullable=False,
                            autoIncrement=None,
                            defaultValue=None,
                            description=None,
                            name=None,
                            type=TextProperty(),
                        )
                    },
                )
            ],
        ),
        id="One view, one container, one property",
    )


class TestDMSTableImporter:
    @pytest.mark.parametrize("data,expected", list(test_valid_dms_table_format()))
    def test_import(self, data: dict[str, list[dict[str, CellValue]]], expected: RequestSchema) -> None:
        importer = DMSTableImporter(data)
        result = importer.to_data_model()
        assert result.model_dump() == expected.model_dump()
