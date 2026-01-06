from typing import cast

from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.validation.dms import (
    ConnectionValueTypeUndefined,
    ConnectionValueTypeUnexisting,
    DmsDataModelValidation,
    ExternalContainerDoesNotExist,
    ExternalContainerPropertyDoesNotExist,
    ImplementedViewNotExisting,
    MappedContainersMissingRequiresConstraint,
    ReverseConnectionSourceViewMissing,
    ViewSpaceVersionInconsistentWithDataModel,
    ViewToContainerMappingNotPossible,
)
from cognite.neat._data_model.validation.dms._containers import RequiredContainerDoesNotExist
from cognite.neat._data_model.validation.dms._limits import ViewPropertyCountIsOutOfLimits
from cognite.neat._issues import IssueList
from tests.data import SNAPSHOT_CATALOG


class TestValidators:
    def test_additive_modus_operandi(self) -> None:
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            local_scenario_name="uncategorized_validators",
            cdf_scenario_name="for_validators",
            modus_operandi="additive",
            include_cdm=False,
            format="snapshots",
        )
        data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

        on_success = DmsDataModelValidation(cdf_snapshot=cdf_snapshot, limits=SchemaLimits(), modus_operandi="additive")

        on_success.run(data_model)

        by_code = cast(IssueList, on_success.issues).by_code()

        assert len(on_success.issues) == 25
        assert set(by_code.keys()) == {
            ConnectionValueTypeUnexisting.code,
            ConnectionValueTypeUndefined.code,
            ViewSpaceVersionInconsistentWithDataModel.code,
            ViewToContainerMappingNotPossible.code,
            ViewPropertyCountIsOutOfLimits.code,
            ReverseConnectionSourceViewMissing.code,
            ExternalContainerDoesNotExist.code,
            ExternalContainerPropertyDoesNotExist.code,
            RequiredContainerDoesNotExist.code,
            MappedContainersMissingRequiresConstraint.code,
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

        assert len(by_code[ViewSpaceVersionInconsistentWithDataModel.code]) == 5
        version_space_inconsistency_messages = [
            issue.message for issue in by_code[ViewSpaceVersionInconsistentWithDataModel.code]
        ]
        expected_inconsistent_views = {
            "another_space:HasPropertiesInCDF(version=v2)",
            "another_space:MissingProperties(version=v2)",
            "my_space:MissingProperties(version=v2)",
            "prodigy:OutOfSpace(version=1992)",
            "not_my_space:ExistingEdgeConnection(version=v1)",
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

        assert len(by_code[ViewPropertyCountIsOutOfLimits.code]) == 5

        missing_view_properties_messages = [issue.message for issue in by_code[ViewPropertyCountIsOutOfLimits.code]]
        expected_views = {
            "another_space:MissingProperties(version=v2)",
            "my_space:MissingProperties(version=v2)",
            "my_space:DomainDescribable(version=v1)",
            "not_my_space:ExistingEdgeConnection(version=v1)",
            "my_space:ExistingDirectConnectionRemote(version=v1)",
        }

        found_views = set()
        for message in missing_view_properties_messages:
            for expected_view in expected_views:
                if expected_view in message:
                    found_views.add(expected_view)

        assert found_views == expected_views

        assert len(by_code[ExternalContainerDoesNotExist.code]) == 1
        assert "nospace:UnexistingContainer" in by_code[ExternalContainerDoesNotExist.code][0].message

        assert len(by_code[ExternalContainerPropertyDoesNotExist.code]) == 1
        assert "unexistingProperty" in by_code[ExternalContainerPropertyDoesNotExist.code][0].message

        assert len(by_code[RequiredContainerDoesNotExist.code]) == 2

        expected_missing_items = {"idonotexist:AndWillNeverExist", "my_space:SomethingThatDoesNotExist"}
        found_missing_items = set()
        for issue in by_code[RequiredContainerDoesNotExist.code]:
            for expected_item in expected_missing_items:
                if expected_item in issue.message:
                    found_missing_items.add(expected_item)
        assert found_missing_items == expected_missing_items

    def test_rebuild_modus_operandi(self) -> None:
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            local_scenario_name="uncategorized_validators",
            cdf_scenario_name="for_validators",
            modus_operandi="rebuild",
            include_cdm=False,
            format="snapshots",
        )
        data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

        on_success = DmsDataModelValidation(cdf_snapshot=cdf_snapshot, limits=SchemaLimits(), modus_operandi="rebuild")

        on_success.run(data_model)

        by_code = cast(IssueList, on_success.issues).by_code()

        assert len(on_success.issues) == 26
        assert set(by_code.keys()) == {
            ConnectionValueTypeUnexisting.code,
            ConnectionValueTypeUndefined.code,
            ViewSpaceVersionInconsistentWithDataModel.code,
            ViewToContainerMappingNotPossible.code,
            ViewPropertyCountIsOutOfLimits.code,
            ReverseConnectionSourceViewMissing.code,
            ExternalContainerDoesNotExist.code,
            ExternalContainerPropertyDoesNotExist.code,
            RequiredContainerDoesNotExist.code,
            ImplementedViewNotExisting.code,
            MappedContainersMissingRequiresConstraint.code,
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

        assert len(by_code[ViewSpaceVersionInconsistentWithDataModel.code]) == 3
        version_space_inconsistency_messages = [
            issue.message for issue in by_code[ViewSpaceVersionInconsistentWithDataModel.code]
        ]
        expected_inconsistent_views = {
            "another_space:HasPropertiesInCDF(version=v2)",
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

        assert len(by_code[ViewToContainerMappingNotPossible.code]) == 4
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

        assert len(by_code[ImplementedViewNotExisting.code]) == 1
        assert "my_space:DomainDescribable(version=v1)" in by_code[ImplementedViewNotExisting.code][0].message

        assert len(by_code[ExternalContainerDoesNotExist.code]) == 1
        assert "nospace:UnexistingContainer" in by_code[ExternalContainerDoesNotExist.code][0].message

        assert len(by_code[ExternalContainerPropertyDoesNotExist.code]) == 1
        assert "unexistingProperty" in by_code[ExternalContainerPropertyDoesNotExist.code][0].message

        expected_missing_items = {"idonotexist:AndWillNeverExist", "my_space:SomethingThatDoesNotExist"}
        found_missing_items = set()
        for issue in by_code[RequiredContainerDoesNotExist.code]:
            for expected_item in expected_missing_items:
                if expected_item in issue.message:
                    found_missing_items.add(expected_item)
        assert found_missing_items == expected_missing_items
