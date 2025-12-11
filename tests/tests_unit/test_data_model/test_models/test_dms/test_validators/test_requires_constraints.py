"""Tests for requires constraint validators."""

from pathlib import Path
from unittest.mock import MagicMock

from cognite.neat._client.client import NeatClient
from cognite.neat._data_model.importers._table_importer.importer import DMSTableImporter
from cognite.neat._data_model.validation.dms._containers import (
    MissingRequiresConstraint,
    RequiresConstraintComplicatesIngestion,
    RequiresConstraintCycle,
    UnnecessaryRequiresConstraint,
)
from cognite.neat._data_model.validation.dms._orchestrator import DmsDataModelValidation


class TestMissingRequiresConstraint:
    """Tests for MissingRequiresConstraint validator."""

    def test_recommends_constraint_when_containers_always_appear_together(
        self, validation_test_cdf_client: NeatClient
    ) -> None:
        """When container A always appears with container B, recommend A requires B."""
        yaml = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
- Key: name
  Value: Test Model
- Key: description
  Value: Test Description
Properties:
- View: AssetView
  View Property: name
  Name: name
  Description: Name property
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:AssetContainer
  Container Property: name
- View: AssetView
  View Property: description
  Name: description
  Description: Description property
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:DescribableContainer
  Container Property: description
Views:
- View: AssetView
  Name: Asset View
  Description: A view mapping to both containers
Containers:
- Container: my_space:AssetContainer
  Used For: node
- Container: my_space:DescribableContainer
  Used For: node
"""
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        validation = DmsDataModelValidation(validation_test_cdf_client)
        validation.run(data_model)

        missing_requires_issues = [issue for issue in validation.issues if issue.code == MissingRequiresConstraint.code]

        # Should recommend AssetContainer requires DescribableContainer (or vice versa)
        assert len(missing_requires_issues) >= 1
        messages = [issue.message for issue in missing_requires_issues]
        assert any("AssetContainer" in msg and "DescribableContainer" in msg for msg in messages)

    def test_no_recommendation_when_constraint_already_exists(self, validation_test_cdf_client: NeatClient) -> None:
        """When A already requires B, no recommendation should be made."""
        yaml = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
- Key: name
  Value: Test Model
- Key: description
  Value: Test Description
Properties:
- View: AssetView
  View Property: name
  Name: name
  Description: Name property
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:AssetContainer
  Container Property: name
- View: AssetView
  View Property: description
  Name: description
  Description: Description property
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:DescribableContainer
  Container Property: description
Views:
- View: AssetView
  Name: Asset View
  Description: A view mapping to both containers
Containers:
- Container: my_space:AssetContainer
  Used For: node
  Constraint: requires:req_describable(require=my_space:DescribableContainer)
- Container: my_space:DescribableContainer
  Used For: node
"""
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        validation = DmsDataModelValidation(validation_test_cdf_client)
        validation.run(data_model)

        missing_requires_issues = [issue for issue in validation.issues if issue.code == MissingRequiresConstraint.code]

        # AssetContainer already requires DescribableContainer, so no recommendation for that direction
        # DescribableContainer doesn't require AssetContainer, so one recommendation might appear for that direction
        messages = [issue.message for issue in missing_requires_issues]
        # Should NOT recommend AssetContainer requires DescribableContainer (already exists)
        # The message format is "Container 'X' is always used together with container 'Y'"
        # So we need to check that AssetContainer is NOT the first container in the message
        assert not any(
            msg.startswith("Container 'my_space:AssetContainer'") and "DescribableContainer" in msg for msg in messages
        )

    def test_transitivity_avoids_redundant_recommendations(self, validation_test_cdf_client: NeatClient) -> None:
        """When B requires C, recommending A requires B should be sufficient (not A requires C)."""
        yaml = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
- Key: name
  Value: Test Model
- Key: description
  Value: Test Description
Properties:
- View: FullView
  View Property: name
  Name: name
  Description: Name property
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:ContainerA
  Container Property: name
- View: FullView
  View Property: code
  Name: code
  Description: Code property
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:ContainerB
  Container Property: code
- View: FullView
  View Property: description
  Name: description
  Description: Description property
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:ContainerC
  Container Property: description
Views:
- View: FullView
  Name: Full View
  Description: A view mapping to all three containers
Containers:
- Container: my_space:ContainerA
  Used For: node
- Container: my_space:ContainerB
  Used For: node
  Constraint: requires:req_c(require=my_space:ContainerC)
- Container: my_space:ContainerC
  Used For: node
"""
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        validation = DmsDataModelValidation(validation_test_cdf_client)
        validation.run(data_model)

        missing_requires_issues = [issue for issue in validation.issues if issue.code == MissingRequiresConstraint.code]

        messages = [issue.message for issue in missing_requires_issues]

        # Should recommend A requires B (which transitively covers C)
        # The message format is "Container 'X' is always used together with container 'Y'"
        a_requires_b = any(
            msg.startswith("Container 'my_space:ContainerA'") and "ContainerB" in msg for msg in messages
        )

        # Should NOT recommend A requires C directly (because B already requires C)
        # Check that there's no "always used together" recommendation for A -> C
        a_requires_c_direct = any(
            msg.startswith("Container 'my_space:ContainerA'") and "always used together" in msg and "ContainerC" in msg
            for msg in messages
        )

        assert a_requires_b, f"Should recommend ContainerA requires ContainerB. Messages: {messages}"
        assert not a_requires_c_direct, (
            f"Should NOT directly recommend ContainerA requires ContainerC. Messages: {messages}"
        )

    def test_recommends_at_correct_level_in_chain(self, validation_test_cdf_client: NeatClient) -> None:
        """
        Scenario:
        - Field requires Asset (existing)
        - Asset and CogniteAsset always appear together (but Asset doesn't require CogniteAsset)

        Should recommend:
        - Asset requires CogniteAsset (NOT Field requires CogniteAsset)
        """
        yaml = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
- Key: name
  Value: Test Model
- Key: description
  Value: Test Description
Properties:
- View: FullView
  View Property: fieldId
  Name: fieldId
  Description: Field ID
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:FieldContainer
  Container Property: fieldId
- View: FullView
  View Property: assetId
  Name: assetId
  Description: Asset ID
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:AssetContainer
  Container Property: assetId
- View: FullView
  View Property: cogniteAssetId
  Name: cogniteAssetId
  Description: Cognite Asset ID
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:CogniteAssetContainer
  Container Property: cogniteAssetId
Views:
- View: FullView
  Name: Full View
  Description: View with all three containers
Containers:
- Container: my_space:FieldContainer
  Used For: node
  Constraint: requires:req_asset(require=my_space:AssetContainer)
- Container: my_space:AssetContainer
  Used For: node
- Container: my_space:CogniteAssetContainer
  Used For: node
"""
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        validation = DmsDataModelValidation(validation_test_cdf_client)
        validation.run(data_model)

        missing_requires_issues = [issue for issue in validation.issues if issue.code == MissingRequiresConstraint.code]

        messages = [issue.message for issue in missing_requires_issues]

        # Should recommend Asset requires CogniteAsset (they always appear together)
        asset_requires_cognite = any(
            msg.startswith("Container 'my_space:AssetContainer'")
            and "always used together" in msg
            and "CogniteAssetContainer" in msg
            for msg in messages
        )

        # Should NOT recommend Field requires CogniteAsset (Field already requires Asset, and Asset should require CogniteAsset)
        field_requires_cognite = any(
            msg.startswith("Container 'my_space:FieldContainer'")
            and "always used together" in msg
            and "CogniteAssetContainer" in msg
            for msg in messages
        )

        assert asset_requires_cognite, (
            f"Should recommend AssetContainer requires CogniteAssetContainer. Messages: {messages}"
        )
        assert not field_requires_cognite, (
            f"Should NOT recommend FieldContainer requires CogniteAssetContainer. Messages: {messages}"
        )

    def test_better_coverage_recommendation(self, validation_test_cdf_client: NeatClient) -> None:
        """
        Scenario:
        - TagReduced view: Tag, CogniteDescribable
        - Tag view: Tag, CogniteAsset, CogniteDescribable
        - CogniteAsset requires CogniteDescribable

        Should recommend:
        1. Tag requires CogniteDescribable (always together)
        2. Tag could require CogniteAsset for better coverage (soft recommendation)
        """
        yaml = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
- Key: name
  Value: Test Model
- Key: description
  Value: Test Description
Properties:
# TagReduced view properties
- View: TagReducedView
  View Property: tagId
  Name: tagId
  Description: Tag ID
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:TagContainer
  Container Property: tagId
- View: TagReducedView
  View Property: description
  Name: description
  Description: Description
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:DescribableContainer
  Container Property: description
# Tag view properties
- View: TagView
  View Property: tagId
  Name: tagId
  Description: Tag ID
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:TagContainer
  Container Property: tagId
- View: TagView
  View Property: assetName
  Name: assetName
  Description: Asset name
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:AssetContainer
  Container Property: assetName
- View: TagView
  View Property: description
  Name: description
  Description: Description
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:DescribableContainer
  Container Property: description
Views:
- View: TagReducedView
  Name: TagReduced View
  Description: TagReduced view with Tag and Describable
- View: TagView
  Name: Tag View
  Description: Tag view with Tag, Asset, and Describable
Containers:
- Container: my_space:TagContainer
  Used For: node
- Container: my_space:AssetContainer
  Used For: node
  Constraint: requires:req_describable(require=my_space:DescribableContainer)
- Container: my_space:DescribableContainer
  Used For: node
"""
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        validation = DmsDataModelValidation(validation_test_cdf_client)
        validation.run(data_model)

        missing_requires_issues = [issue for issue in validation.issues if issue.code == MissingRequiresConstraint.code]

        messages = [issue.message for issue in missing_requires_issues]

        # Should recommend Tag requires Describable (always together)
        tag_requires_describable = any(
            "TagContainer" in msg and "always used together" in msg and "DescribableContainer" in msg
            for msg in messages
        )

        # Should suggest AssetContainer as better coverage option
        better_coverage = any(
            "TagContainer" in msg and "AssetContainer" in msg and "better" in msg.lower() for msg in messages
        )

        assert tag_requires_describable, "Should recommend TagContainer requires DescribableContainer"
        assert better_coverage, "Should suggest AssetContainer as better coverage option"


class TestUnnecessaryRequiresConstraint:
    """Tests for UnnecessaryRequiresConstraint validator."""

    def test_detects_unnecessary_constraint(self, validation_test_cdf_client: NeatClient) -> None:
        """When containers with requires constraint never appear together, flag it."""
        yaml = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
- Key: name
  Value: Test Model
- Key: description
  Value: Test Description
Properties:
- View: OrderView
  View Property: orderId
  Name: orderId
  Description: Order ID
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:OrderContainer
  Container Property: orderId
- View: CustomerView
  View Property: customerId
  Name: customerId
  Description: Customer ID
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:CustomerContainer
  Container Property: customerId
Views:
- View: OrderView
  Name: Order View
  Description: Order view
- View: CustomerView
  Name: Customer View
  Description: Customer view
Containers:
- Container: my_space:OrderContainer
  Used For: node
  Constraint: requires:req_customer(require=my_space:CustomerContainer)
- Container: my_space:CustomerContainer
  Used For: node
"""
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        validation = DmsDataModelValidation(validation_test_cdf_client)
        validation.run(data_model)

        unnecessary_issues = [issue for issue in validation.issues if issue.code == UnnecessaryRequiresConstraint.code]

        assert len(unnecessary_issues) == 1
        assert "OrderContainer" in unnecessary_issues[0].message
        assert "CustomerContainer" in unnecessary_issues[0].message
        assert "never appear together" in unnecessary_issues[0].message

    def test_no_issue_when_constraint_is_valid(self, validation_test_cdf_client: NeatClient) -> None:
        """When containers with requires constraint DO appear together, no issue."""
        yaml = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
- Key: name
  Value: Test Model
- Key: description
  Value: Test Description
Properties:
- View: CombinedView
  View Property: orderId
  Name: orderId
  Description: Order ID
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:OrderContainer
  Container Property: orderId
- View: CombinedView
  View Property: customerId
  Name: customerId
  Description: Customer ID
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:CustomerContainer
  Container Property: customerId
Views:
- View: CombinedView
  Name: Combined View
  Description: Combined view with both containers
Containers:
- Container: my_space:OrderContainer
  Used For: node
  Constraint: requires:req_customer(require=my_space:CustomerContainer)
- Container: my_space:CustomerContainer
  Used For: node
"""
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        validation = DmsDataModelValidation(validation_test_cdf_client)
        validation.run(data_model)

        unnecessary_issues = [issue for issue in validation.issues if issue.code == UnnecessaryRequiresConstraint.code]

        assert len(unnecessary_issues) == 0


class TestRequiresConstraintCycle:
    """Tests for RequiresConstraintCycle validator."""

    def test_detects_simple_cycle(self, validation_test_cdf_client: NeatClient) -> None:
        """Detects A -> B -> A cycle."""
        yaml = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
- Key: name
  Value: Test Model
- Key: description
  Value: Test Description
Properties:
- View: TestView
  View Property: propA
  Name: propA
  Description: Property A
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:ContainerA
  Container Property: propA
- View: TestView
  View Property: propB
  Name: propB
  Description: Property B
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:ContainerB
  Container Property: propB
Views:
- View: TestView
  Name: Test View
  Description: Test view
Containers:
- Container: my_space:ContainerA
  Used For: node
  Constraint: requires:req_b(require=my_space:ContainerB)
- Container: my_space:ContainerB
  Used For: node
  Constraint: requires:req_a(require=my_space:ContainerA)
"""
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        validation = DmsDataModelValidation(validation_test_cdf_client)
        validation.run(data_model)

        cycle_issues = [issue for issue in validation.issues if issue.code == RequiresConstraintCycle.code]

        assert len(cycle_issues) == 1
        assert "cycle" in cycle_issues[0].message.lower()
        assert "ContainerA" in cycle_issues[0].message
        assert "ContainerB" in cycle_issues[0].message

    def test_detects_longer_cycle(self, validation_test_cdf_client: NeatClient) -> None:
        """Detects A -> B -> C -> A cycle."""
        yaml = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
- Key: name
  Value: Test Model
- Key: description
  Value: Test Description
Properties:
- View: TestView
  View Property: propA
  Name: propA
  Description: Property A
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:ContainerA
  Container Property: propA
- View: TestView
  View Property: propB
  Name: propB
  Description: Property B
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:ContainerB
  Container Property: propB
- View: TestView
  View Property: propC
  Name: propC
  Description: Property C
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:ContainerC
  Container Property: propC
Views:
- View: TestView
  Name: Test View
  Description: Test view
Containers:
- Container: my_space:ContainerA
  Used For: node
  Constraint: requires:req_b(require=my_space:ContainerB)
- Container: my_space:ContainerB
  Used For: node
  Constraint: requires:req_c(require=my_space:ContainerC)
- Container: my_space:ContainerC
  Used For: node
  Constraint: requires:req_a(require=my_space:ContainerA)
"""
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        validation = DmsDataModelValidation(validation_test_cdf_client)
        validation.run(data_model)

        cycle_issues = [issue for issue in validation.issues if issue.code == RequiresConstraintCycle.code]

        assert len(cycle_issues) == 1
        assert "cycle" in cycle_issues[0].message.lower()

    def test_no_cycle_for_linear_chain(self, validation_test_cdf_client: NeatClient) -> None:
        """No cycle when A -> B -> C (linear chain)."""
        yaml = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
- Key: name
  Value: Test Model
- Key: description
  Value: Test Description
Properties:
- View: TestView
  View Property: propA
  Name: propA
  Description: Property A
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:ContainerA
  Container Property: propA
- View: TestView
  View Property: propB
  Name: propB
  Description: Property B
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:ContainerB
  Container Property: propB
- View: TestView
  View Property: propC
  Name: propC
  Description: Property C
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:ContainerC
  Container Property: propC
Views:
- View: TestView
  Name: Test View
  Description: Test view
Containers:
- Container: my_space:ContainerA
  Used For: node
  Constraint: requires:req_b(require=my_space:ContainerB)
- Container: my_space:ContainerB
  Used For: node
  Constraint: requires:req_c(require=my_space:ContainerC)
- Container: my_space:ContainerC
  Used For: node
"""
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        validation = DmsDataModelValidation(validation_test_cdf_client)
        validation.run(data_model)

        cycle_issues = [issue for issue in validation.issues if issue.code == RequiresConstraintCycle.code]

        assert len(cycle_issues) == 0


class TestRequiresConstraintComplicatesIngestion:
    """Tests for RequiresConstraintComplicatesIngestion validator."""

    def test_detects_ingestion_complication(self, validation_test_cdf_client: NeatClient) -> None:
        """
        When A requires B, B has non-nullable properties, and no view maps to both A and B's non-nullable props.
        """
        yaml = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
- Key: name
  Value: Test Model
- Key: description
  Value: Test Description
Properties:
# View maps only to AssetContainer, not to DescribableContainer
- View: AssetOnlyView
  View Property: assetId
  Name: assetId
  Description: Asset ID
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:AssetContainer
  Container Property: assetId
# Separate view maps only to DescribableContainer with non-nullable property (Min Count: 1)
- View: DescribableOnlyView
  View Property: name
  Name: name
  Description: Name property
  Value Type: text
  Min Count: 1
  Max Count: 1
  Connection: null
  Container: my_space:DescribableContainer
  Container Property: name
Views:
- View: AssetOnlyView
  Name: Asset Only View
  Description: View mapping only to AssetContainer
- View: DescribableOnlyView
  Name: Describable Only View
  Description: View mapping only to DescribableContainer
Containers:
- Container: my_space:AssetContainer
  Used For: node
  Constraint: requires:req_describable(require=my_space:DescribableContainer)
- Container: my_space:DescribableContainer
  Used For: node
"""
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        validation = DmsDataModelValidation(validation_test_cdf_client)
        validation.run(data_model)

        issues = [issue for issue in validation.issues if issue.code == RequiresConstraintComplicatesIngestion.code]

        assert len(issues) == 1
        assert "AssetContainer" in issues[0].message
        assert "DescribableContainer" in issues[0].message
        assert "non-nullable" in issues[0].message.lower()

    def test_no_issue_when_view_covers_both_containers(self, validation_test_cdf_client: NeatClient) -> None:
        """When a view maps to both A and all non-nullable properties of B, no issue."""
        yaml = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
- Key: name
  Value: Test Model
- Key: description
  Value: Test Description
Properties:
# View maps to both containers including the non-nullable property (Min Count: 1)
- View: CombinedView
  View Property: assetId
  Name: assetId
  Description: Asset ID
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:AssetContainer
  Container Property: assetId
- View: CombinedView
  View Property: name
  Name: name
  Description: Name property
  Value Type: text
  Min Count: 1
  Max Count: 1
  Connection: null
  Container: my_space:DescribableContainer
  Container Property: name
Views:
- View: CombinedView
  Name: Combined View
  Description: View mapping to both containers
Containers:
- Container: my_space:AssetContainer
  Used For: node
  Constraint: requires:req_describable(require=my_space:DescribableContainer)
- Container: my_space:DescribableContainer
  Used For: node
"""
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        validation = DmsDataModelValidation(validation_test_cdf_client)
        validation.run(data_model)

        issues = [issue for issue in validation.issues if issue.code == RequiresConstraintComplicatesIngestion.code]

        assert len(issues) == 0

    def test_no_issue_when_required_container_has_no_non_nullable_properties(
        self, validation_test_cdf_client: NeatClient
    ) -> None:
        """When B has no non-nullable properties, no issue (ingestion is straightforward)."""
        yaml = """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
- Key: name
  Value: Test Model
- Key: description
  Value: Test Description
Properties:
# View maps only to AssetContainer
- View: AssetOnlyView
  View Property: assetId
  Name: assetId
  Description: Asset ID
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:AssetContainer
  Container Property: assetId
# Separate view maps to DescribableContainer (with nullable property - Min Count: 0)
- View: DescribableOnlyView
  View Property: description
  Name: description
  Description: Description property
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:DescribableContainer
  Container Property: description
Views:
- View: AssetOnlyView
  Name: Asset Only View
  Description: View mapping only to AssetContainer
- View: DescribableOnlyView
  Name: Describable Only View
  Description: View mapping only to DescribableContainer
Containers:
- Container: my_space:AssetContainer
  Used For: node
  Constraint: requires:req_describable(require=my_space:DescribableContainer)
- Container: my_space:DescribableContainer
  Used For: node
"""
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml
        importer = DMSTableImporter.from_yaml(read_yaml)
        data_model = importer.to_data_model()

        validation = DmsDataModelValidation(validation_test_cdf_client)
        validation.run(data_model)

        issues = [issue for issue in validation.issues if issue.code == RequiresConstraintComplicatesIngestion.code]

        assert len(issues) == 0
