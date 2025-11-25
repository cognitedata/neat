from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from cognite.neat._client.client import NeatClient
from cognite.neat._data_model.importers._table_importer.importer import DMSTableImporter
from cognite.neat._data_model.validation.dms import (
    ConnectionValueTypeUndefined,
    ConnectionValueTypeUnexisting,
    DmsDataModelValidation,
    ReverseConnectionSourceViewMissing,
    ViewSpaceVersionInconsistentWithDataModel,
    ViewToContainerMappingNotPossible,
)
from cognite.neat._data_model.validation.dms._limits import ViewPropertyCountIsOutOfLimits
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
  View Property: directLocal
  Connection: direct
  Value Type: my_space:UnexistingDirectConnectionLocal(version=v1)
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: my_space:DirectConnectionContainer
  Container Property: directLocal
- View: MyDescribable
  View Property: directToNowhere
  Connection: direct
  Value Type: '#N/A'
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: my_space:DirectConnectionContainer
  Container Property: directToNowhere
- View: MyDescribable
  View Property: directRemote
  Connection: direct
  Value Type: my_space:ExistingDirectConnectionRemote(version=v1)
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: my_space:DirectConnectionRemoteContainer
  Container Property: directRemote
- View: MyDescribable
  View Property: singleEdgeProperty
  Connection: edge(type=MyDescribable.singleEdgeProperty)
  Value Type: not_my_space:ExistingEdgeConnection(version=v1)
  Min Count: 0
  Max Count: 1
- View: MyDescribable
  View Property: singleEdgePropertyToMyView
  Connection: edge(type=MyDescribable.singleEdgeProperty)
  Value Type: my_space:UnexistingEdgeConnection(version=v1)
  Min Count: 0
  Max Count: 1
- View: MyDescribable
  View Property: reverseDirectPropertyRemote
  Connection: reverse(property=directPropertyRemote)
  Value Type: my_space:SourceForReverseConnectionExistRemote(version=v1)
  Min Count: 0
  Max Count: 1
- View: MyDescribable
  View Property: reverseDirectPropertyMissingOtherEnd
  Connection: reverse(property=directPropertyLocal)
  Value Type: my_space:UnexistingSourceForReverseConnection(version=v1)
  Min Count: 0
  Max Count: 1
Views:
- View: MyDescribable
- View: another_space:MissingProperties(version=v2)
- View: my_space:MissingProperties(version=v2)
Containers:
- Container: cdf_cdm:CogniteDescribable
  Used For: node
- Container: my_space:DirectConnectionContainer
  Used For: node
"""


class TestValidators:
    def test_additive_modus_operandi(
        self, validation_test_cdf_client: NeatClient, valid_dms_yaml_with_consistency_errors: str
    ) -> None:
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = valid_dms_yaml_with_consistency_errors
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        on_success = DmsDataModelValidation(validation_test_cdf_client, modus_operandi="additive")

        on_success.run(data_model)

        by_code = cast(IssueList, on_success.issues).by_code()

        assert len(on_success.issues) == 11
        assert set(by_code.keys()) == {
            ConnectionValueTypeUnexisting.code,
            ConnectionValueTypeUndefined.code,
            ViewSpaceVersionInconsistentWithDataModel.code,
            ViewToContainerMappingNotPossible.code,
            ViewPropertyCountIsOutOfLimits.code,
            ReverseConnectionSourceViewMissing.code,
        }

        assert len(by_code[ConnectionValueTypeUnexisting.code]) == 3

        undefined_connection_messages = [issue.message for issue in by_code[ConnectionValueTypeUnexisting.code]]
        expected_connections = {
            "my_space:UnexistingDirectConnectionLocal(version=v1)",
            "my_space:UnexistingSourceForReverseConnection(version=v1)",
            "my_space:UnexistingEdgeConnection(version=v1)",
        }

        # Check that all expected connections are mentioned in the messages
        found_connections = set()
        for message in undefined_connection_messages:
            for expected_connection in expected_connections:
                if expected_connection in message:
                    found_connections.add(expected_connection)

        assert found_connections == expected_connections

        assert len(by_code[ViewSpaceVersionInconsistentWithDataModel.code]) == 2
        version_space_inconsistency_messages = [
            issue.message for issue in by_code[ViewSpaceVersionInconsistentWithDataModel.code]
        ]
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

        assert len(by_code[ConnectionValueTypeUndefined.code]) == 1
        assert "directToNowhere" in by_code[ConnectionValueTypeUndefined.code][0].message

        assert len(by_code[ReverseConnectionSourceViewMissing.code]) == 1
        assert "reverseDirectPropertyMissingOtherEnd" in by_code[ReverseConnectionSourceViewMissing.code][0].message

        assert len(by_code[ViewToContainerMappingNotPossible.code]) == 2
        referenced_containers_messages = [issue.message for issue in by_code[ViewToContainerMappingNotPossible.code]]
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

        assert len(by_code[ViewPropertyCountIsOutOfLimits.code]) == 2

        missing_view_properties_messages = [issue.message for issue in by_code[ViewPropertyCountIsOutOfLimits.code]]
        expected_views = {"another_space:MissingProperties(version=v2)", "my_space:MissingProperties(version=v2)"}

        found_views = set()
        for message in missing_view_properties_messages:
            for expected_view in expected_views:
                if expected_view in message:
                    found_views.add(expected_view)

        assert found_views == expected_views

    def test_rebuild_modus_operandi(
        self, validation_test_cdf_client: NeatClient, valid_dms_yaml_with_consistency_errors: str
    ) -> None:
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = valid_dms_yaml_with_consistency_errors
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        on_success = DmsDataModelValidation(validation_test_cdf_client, modus_operandi="rebuild")

        on_success.run(data_model)

        by_code = cast(IssueList, on_success.issues).by_code()

        assert len(on_success.issues) == 15
        assert set(by_code.keys()) == {
            ConnectionValueTypeUnexisting.code,
            ConnectionValueTypeUndefined.code,
            ViewSpaceVersionInconsistentWithDataModel.code,
            ReverseConnectionSourceViewMissing.code,
            ViewToContainerMappingNotPossible.code,
            ViewPropertyCountIsOutOfLimits.code,
        }

        assert len(by_code[ConnectionValueTypeUnexisting.code]) == 5

        undefined_connection_messages = [issue.message for issue in by_code[ConnectionValueTypeUnexisting.code]]
        expected_connections = {
            "my_space:UnexistingDirectConnectionLocal(version=v1)",
            "my_space:UnexistingSourceForReverseConnection(version=v1)",
            "my_space:UnexistingEdgeConnection(version=v1)",
            "my_space:SourceForReverseConnectionExistRemote(version=v1)",
        }

        # Check that all expected connections are mentioned in the messages
        found_connections = set()
        for message in undefined_connection_messages:
            for expected_connection in expected_connections:
                if expected_connection in message:
                    found_connections.add(expected_connection)

        assert found_connections == expected_connections

        assert len(by_code[ViewSpaceVersionInconsistentWithDataModel.code]) == 2
        version_space_inconsistency_messages = [
            issue.message for issue in by_code[ViewSpaceVersionInconsistentWithDataModel.code]
        ]
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

        assert len(by_code[ReverseConnectionSourceViewMissing.code]) == 2
        expected_affected_reverse_properties = {"reverseDirectPropertyMissingOtherEnd", "reverseDirectPropertyRemote"}

        assert len(by_code[ConnectionValueTypeUndefined.code]) == 1
        assert "directToNowhere" in by_code[ConnectionValueTypeUndefined.code][0].message

        found_affected_reverse_properties = set()
        for message in by_code[ReverseConnectionSourceViewMissing.code]:
            for expected_property in expected_affected_reverse_properties:
                if expected_property in message.message:
                    found_affected_reverse_properties.add(expected_property)
        assert found_affected_reverse_properties == expected_affected_reverse_properties

        assert len(by_code[ViewToContainerMappingNotPossible.code]) == 3
        referenced_containers_messages = [issue.message for issue in by_code[ViewToContainerMappingNotPossible.code]]
        expected_missing_containers = {"nospace:UnexistingContainer", "my_space:DirectConnectionRemoteContainer"}
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
