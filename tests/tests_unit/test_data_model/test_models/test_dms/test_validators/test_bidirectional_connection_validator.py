from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cognite.neat._client.client import NeatClient
from cognite.neat._data_model.importers._table_importer.importer import DMSTableImporter
from cognite.neat._data_model.models.dms._references import ContainerDirectReference, ContainerReference, ViewReference
from cognite.neat._data_model.models.dms._view_property import SingleReverseDirectRelationPropertyRequest
from cognite.neat._data_model.validation.dms import (
    DmsDataModelValidation,
    ReverseConnectionContainerMissing,
    ReverseConnectionContainerPropertyMissing,
    ReverseConnectionContainerPropertyWrongType,
    ReverseConnectionPointsToAncestor,
    ReverseConnectionSourcePropertyMissing,
    ReverseConnectionSourcePropertyWrongType,
    ReverseConnectionSourceViewMissing,
    ReverseConnectionTargetMismatch,
    ReverseConnectionTargetMissing,
)


@pytest.fixture(scope="session")
def valid_dms_yaml_with_consistency_errors() -> tuple[str, dict[str, set]]:
    yaml_content = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
Properties:

- View: AncestorView
  View Property: outerReflection
  Connection: direct
  Value Type: AncestorView
  Min Count: 0
  Max Count: 1
  Container: AncestorContainer
  Container Property: outerReflectionStorage

- View: AncestorView
  View Property: innerReflection
  Connection: reverse(property=outerReflection)
  Value Type: AncestorView
  Min Count: 0
  Max Count: 1

# Simulates when inherited direct was not updated
- View: DescendantView
  View Property: innerReflection
  Connection: reverse(property=outerReflection)
  Value Type: DescendantView
  Min Count: 0
  Max Count: 1

- View: SourceView
  View Property: name
  Connection: null
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: SourceContainer
  Container Property: nameStorage

- View: AnotherView
  View Property: name
  Connection: null
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: AnotherContainer
  Container Property: nameStorage

- View: TargetView
  View Property: name
  Connection: null
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: TargetContainer
  Container Property: nameStorage


- View: SourceView
  View Property: directSourceToAnotheViewConnection
  Connection: direct
  Value Type: AnotherView
  Min Count: 0
  Max Count: 1
  Container: SourceContainer
  Container Property: directConnectionStorage

# Simulates case where niether local nor CDF have the container property
- View: SourceView
  View Property: directConnectionWithoutContainer
  Connection: direct
  Value Type: TargetView
  Min Count: 0
  Max Count: 1
  Container: NoContainer
  Container Property: directConnectionWithoutContainerStorage


# Simulates case where niether local nor CDF have the container property
- View: SourceView
  View Property: directWhichContainerPropertyDoesNotExist
  Connection: direct
  Value Type: TargetView
  Min Count: 0
  Max Count: 1
  Container: SourceContainer
  Container Property: directWhichContainerPropertyDoesNotExistStorage

# Simulates case where niether local nor CDF have the container property
- View: SourceView
  View Property: directWithoutTyping
  Connection: direct
  Value Type: ToBeSetToNone
  Min Count: 0
  Max Count: 1
  Container: SourceContainer
  Container Property: directWithoutTypingStorage

# Simulates case where niether local nor CDF have the container property
- View: SourceView
  View Property: edgeConnection
  Connection: edge
  Value Type: AnotherView
  Min Count: 0
  Max Count: 1
  Container: null
  Container Property: null


- View: AnotherView
  View Property: reverseSourceToAnotheViewConnection
  Connection: reverse(property=directSourceToAnotheViewConnection)
  Value Type: SourceView
  Min Count: 0
  Max Count: 1

# Direct points to AnotherView not to TargetView
- View: TargetView
  View Property: reverseSourceToTargetViewConnection
  Connection: reverse(property=directSourceToAnotheViewConnection)
  Value Type: SourceView
  Min Count: 0
  Max Count: 1

# Unknow view type is not in the data model
- View: TargetView
  View Property: reverseUnknownToTargetViewConnection
  Connection: reverse(property=directSourceToAnotheViewConnection)
  Value Type: Unknown
  Min Count: 0
  Max Count: 1

# direct is edge so this should fail
- View: TargetView
  View Property: reverseToEdgeConnection
  Connection: reverse(property=edgeConnection)
  Value Type: SourceView
  Min Count: 0
  Max Count: 1


# missing container on source
- View: TargetView
  View Property: reverseToDirectConnectionWithoutContainer
  Connection: reverse(property=directConnectionWithoutContainer)
  Value Type: SourceView
  Min Count: 0
  Max Count: 1


# SourceView is missing directDoesNotExist property
- View: TargetView
  View Property: reverseToDirectThatDoesNotExist
  Connection: reverse(property=directDoesNotExist)
  Value Type: SourceView
  Min Count: 0
  Max Count: 1


# View does not have any property
- View: TargetView
  View Property: reverseToViewWithoutProperties
  Connection: reverse(property=directDoesNotExist)
  Value Type: ViewWithoutProperties
  Min Count: 0
  Max Count: 1

# Expected property is not direct connection
- View: TargetView
  View Property: reverseToAttribute
  Connection: reverse(property=name)
  Value Type: SourceView
  Min Count: 0
  Max Count: 1

# direct exists, however container for this property does not exist
# this simulates when nieter CDF nor local have the container defined
- View: TargetView
  View Property: reverseToDirectWhichDoesHaveStorage
  Connection: reverse(property=directWhichContainerPropertyDoesNotExist)
  Value Type: SourceView
  Min Count: 0
  Max Count: 1

# direct exists, however it is not typed, so this will raise Recommendation
- View: TargetView
  View Property: reverseToDirectWithoutTyping
  Connection: reverse(property=directWithoutTyping)
  Value Type: SourceView
  Min Count: 0
  Max Count: 1



Views:
- View: SourceView
- View: TargetView
- View: AnotherView
- View: ViewWithoutProperties
- View: AncestorView
- View: DescendantView
  Implements: AncestorView

Containers:
- Container: SourceContainer
  Used For: node
- Container: TargetContainer
  Used For: node
- Container: AnotherContainer
  Used For: node
- Container: AncestorContainer
  Used For: node
- Container: DescendantContainer
  Used For: node
"""

    expected_problematic_reversals = {
        ReverseConnectionSourceViewMissing.code: {"reverseUnknownToTargetViewConnection"},
        ReverseConnectionSourcePropertyMissing.code: {
            "reverseToDirectThatDoesNotExist",
            "reverseToViewWithoutProperties",
            "reverseThroughContainerDirectReferenceFailing",
        },
        ReverseConnectionSourcePropertyWrongType.code: {"reverseToEdgeConnection"},
        ReverseConnectionContainerMissing.code: {"reverseToDirectConnectionWithoutContainer"},
        ReverseConnectionContainerPropertyMissing.code: {"reverseToDirectWhichDoesHaveStorage"},
        ReverseConnectionContainerPropertyWrongType.code: {"reverseToAttribute"},
        ReverseConnectionTargetMissing.code: {"reverseToAttribute", "reverseToDirectWithoutTyping"},
        ReverseConnectionPointsToAncestor.code: {"innerReflection"},
        ReverseConnectionTargetMismatch.code: {"reverseSourceToTargetViewConnection"},
    }

    return yaml_content, expected_problematic_reversals


def test_validation(
    validation_test_cdf_client: NeatClient, valid_dms_yaml_with_consistency_errors: tuple[str, dict[str, set]]
) -> None:
    yaml_content, expected_problematic_reversals = valid_dms_yaml_with_consistency_errors

    read_yaml = MagicMock(spec=Path)
    read_yaml.read_text.return_value = yaml_content
    importer = DMSTableImporter.from_yaml(read_yaml)
    data_model = importer.to_data_model()

    data_model.containers[0].properties.pop("directWhichContainerPropertyDoesNotExistStorage")

    # simulates undefined end node type by removing the source from the property
    data_model.views[0].properties["directWithoutTyping"].source = None

    # simulates that reverse connection was configured using SDK
    data_model.views[1].properties["reverseThroughContainerDirectReferenceFailing"] = (
        SingleReverseDirectRelationPropertyRequest(
            connection_type="single_reverse_direct_relation",
            name=None,
            description=None,
            source=ViewReference(type="view", space="my_space", external_id="SourceView", version="v1"),
            through=ContainerDirectReference(
                source=ContainerReference(type="container", space="my_space", external_id="SourceContainer"),
                identifier="notImportant",
            ),
        )
    )

    # Run on success validators
    on_success = DmsDataModelValidation(validation_test_cdf_client)
    on_success.run(data_model)

    by_code = on_success.issues.by_code()

    assert set(expected_problematic_reversals.keys()) - set(by_code.keys()) == set()

    # here we check that all expected problematic reversals are found
    found_problematic_reversals = set()
    actual_problematic_reversal = set()
    for code, ill_reverse_connections in expected_problematic_reversals.items():
        for ill_reverse in ill_reverse_connections:
            actual_problematic_reversal.add(ill_reverse)
            for issue in by_code[code]:
                if ill_reverse in issue.message:
                    found_problematic_reversals.add(ill_reverse)
                    break

    assert found_problematic_reversals == actual_problematic_reversal
