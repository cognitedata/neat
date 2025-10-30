from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest
import respx

from cognite.neat._client.client import NeatClient
from cognite.neat._data_model.importers._table_importer.importer import DMSTableImporter
from cognite.neat._data_model.models.dms._validation import (
    DmsDataModelValidation,
    UndefinedConnectionEndNodeTypes,
    ViewsWithoutProperties,
)
from cognite.neat._issues import IssueList


@pytest.fixture()
def client(neat_client: NeatClient, respx_mock: respx.MockRouter) -> NeatClient:
    client = neat_client
    config = client.config
    respx_mock.post(
        config.create_api_url("/models/views/byids?includeInheritedProperties=true"),
    ).respond(
        status_code=200,
        json={
            "items": [],
            "nextCursor": None,
        },
    )

    return client


@pytest.fixture(scope="session")
def valid_dms_yaml_with_consistency_errors() -> str:
    return """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
Properties:
- View: MyDescribable
  View Property: name
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: cdf_cdm:CogniteDescribable
  Container Property: name
  Index: btree:name(cursorable=True)
  Connection: null
- View: MyDescribable
  View Property: source
  Connection: direct
  Value Type: cdf_cdm:UnexistingDirectConnection(version=v1)
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: cdf_cdm:CogniteSourceable
  Container Property: source
- View: MyDescribable
  View Property: singleEdgeProperty
  Connection: edge(type=MyDescribable.singleEdgeProperty)
  Value Type: cdf_cdm:UnexistingEdgeConnection(version=v1)
  Min Count: 0
  Max Count: 1
- View: MyDescribable
  View Property: reverseDirectProperty
  Connection: reverse(property=asset)
  Value Type: cdf_cdm:UnexistingReverseConnection(version=v1)
  Min Count: 0
  Max Count: 1
Views:
- View: MyDescribable
- View: MissingProperties
Containers:
- Container: cdf_cdm:CogniteDescribable
  Used For: node
- Container: cdf_cdm:CogniteSourceable
  Used For: node
"""


def test_validation(client: NeatClient, valid_dms_yaml_with_consistency_errors: str) -> None:
    read_yaml = MagicMock(spec=Path)
    read_yaml.read_text.return_value = valid_dms_yaml_with_consistency_errors
    importer = DMSTableImporter.from_yaml(read_yaml)
    data_model = importer.to_data_model()

    on_success = DmsDataModelValidation(client)

    on_success.run(data_model)

    assert len(on_success.issues) == 4

    by_code = cast(IssueList, on_success.issues).by_code()
    assert set(by_code.keys()) == {ViewsWithoutProperties.code, UndefinedConnectionEndNodeTypes.code}
    assert len(by_code[ViewsWithoutProperties.code]) == 1
    assert len(by_code[UndefinedConnectionEndNodeTypes.code]) == 3
