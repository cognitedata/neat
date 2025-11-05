from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from cognite.neat._client.client import NeatClient
from cognite.neat._data_model.importers._table_importer.importer import DMSTableImporter
from cognite.neat._data_model.validation.dms import (
    BidirectionalConnectionMisconfigured,
    DataModelLimitValidator,
    DmsDataModelValidation,
    ReferencedContainersExist,
    UndefinedConnectionEndNodeTypes,
    VersionSpaceInconsistency,
)
from cognite.neat._issues import IssueList


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
  View Property: altName
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: nospace:UnexistingContainer
  Container Property: altName
  Connection: null
- View: MyDescribable
  View Property: jargon
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: nospace:ExistingContainer
  Container Property: unexistingProperty
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
- View: another_space:MissingProperties(version=v2)
- View: my_space:MissingProperties(version=v2)
Containers:
- Container: cdf_cdm:CogniteDescribable
  Used For: node
- Container: cdf_cdm:CogniteSourceable
  Used For: node
"""


def test_validation(validation_test_cdf_client: NeatClient, valid_dms_yaml_with_consistency_errors: str) -> None:
    read_yaml = MagicMock(spec=Path)
    read_yaml.read_text.return_value = valid_dms_yaml_with_consistency_errors
    importer = DMSTableImporter.from_yaml(read_yaml)
    data_model = importer.to_data_model()

    on_success = DmsDataModelValidation(validation_test_cdf_client)

    on_success.run(data_model)

    by_code = cast(IssueList, on_success.issues).by_code()

    assert len(on_success.issues) == 10
    assert set(by_code.keys()) == {
        UndefinedConnectionEndNodeTypes.code,
        VersionSpaceInconsistency.code,
        BidirectionalConnectionMisconfigured.code,
        ReferencedContainersExist.code,
        DataModelLimitValidator.code,
    }

    assert len(by_code[UndefinedConnectionEndNodeTypes.code]) == 3

    undefined_connection_messages = [issue.message for issue in by_code[UndefinedConnectionEndNodeTypes.code]]
    expected_connections = {
        "cdf_cdm:UnexistingDirectConnection(version=v1)",
        "cdf_cdm:UnexistingReverseConnection(version=v1)",
        "cdf_cdm:UnexistingEdgeConnection(version=v1)",
    }

    # Check that all expected connections are mentioned in the messages
    found_connections = set()
    for message in undefined_connection_messages:
        for expected_connection in expected_connections:
            if expected_connection in message:
                found_connections.add(expected_connection)

    assert found_connections == expected_connections

    assert len(by_code[VersionSpaceInconsistency.code]) == 2
    version_space_inconsistency_messages = [issue.message for issue in by_code[VersionSpaceInconsistency.code]]
    expected_inconsistent_views = {
        "another_space:MissingProperties(version=v2)",
        "my_space:MissingProperties(version=v2)",
    }

    # Check that both expected views are mentioned in the messages
    found_inconsistent_views = set()
    for message in version_space_inconsistency_messages:
        for expected_view in expected_inconsistent_views:
            if expected_view in message:
                found_inconsistent_views.add(expected_view)

    assert found_inconsistent_views == expected_inconsistent_views

    assert len(by_code[BidirectionalConnectionMisconfigured.code]) == 1
    assert "reverseDirectProperty" in by_code[BidirectionalConnectionMisconfigured.code][0].message

    assert len(by_code[ReferencedContainersExist.code]) == 2
    referenced_containers_messages = [issue.message for issue in by_code[ReferencedContainersExist.code]]
    expected_missing_containers = {"nospace:UnexistingContainer"}
    expected_missing_container_properties = {"unexistingProperty"}

    found_missing_containers = set()
    found_missing_container_properties = set()

    for message in referenced_containers_messages:
        for expected_container in expected_missing_containers:
            if expected_container in message:
                found_missing_containers.add(expected_container)
        for expected_property in expected_missing_container_properties:
            if expected_property in message:
                found_missing_container_properties.add(expected_property)

    assert found_missing_containers == expected_missing_containers
    assert found_missing_container_properties == expected_missing_container_properties

    assert len(by_code[DataModelLimitValidator.code]) == 2

    missing_view_properties_messages = [issue.message for issue in by_code[DataModelLimitValidator.code]]
    expected_views = {"another_space:MissingProperties(version=v2)", "my_space:MissingProperties(version=v2)"}

    found_views = set()
    for message in missing_view_properties_messages:
        for expected_view in expected_views:
            if expected_view in message:
                found_views.add(expected_view)

    assert found_views == expected_views
