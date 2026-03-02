""" "Tests that applies to all validators."""

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.importers import DMSTableImporter
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.rules.dms import DataModelRule, DmsDataModelRulesOrchestrator
from cognite.neat._issues import ConsistencyError
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from tests.tests_unit.test_data_model.test_rules.dms.test_alpha_validator import NEAT_TEST_BASE_CODE


class TestValidatorMetaTests:
    """Tests about the properties of the validators themselves."""

    def test_validator_code_uniqueness(self) -> None:
        """Test that all DataModelValidator subclasses have unique codes."""

        # Recursively get all subclasses
        all_validators: list[type[DataModelRule]] = get_concrete_subclasses(DataModelRule)

        # Get all codes
        # The NEAT_TEST_BASE_CODE is used in testing and may be duplicated, as we execute the same test
        # multiple times with different data.
        codes = [validator.code for validator in all_validators if not validator.code.startswith(NEAT_TEST_BASE_CODE)]

        # Check for duplicates
        duplicates = [code for code, count in Counter(codes).items() if count > 1]

        assert len(codes) == len(set(codes)), f"Duplicate validator codes found: {set(duplicates)}"
        assert len(codes) > 0, "No validator codes found - ensure validators have _code attribute"


def consistent_models() -> Iterable[tuple]:
    yield pytest.param(
        """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: MyDataModel
- Key: version
  Value: v1
- Key: creator
  Value: test_user,other_user
Properties:
- View: MyView
  View Property: name
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: another_space:MyContainer
  Container Property: name
  Index: btree:name(cursorable=True)
  Connection: null
Views:
- View: MyView
Containers:
- Container: another_space:MyContainer
  Used For: node
""",
        id="Data model with container in different space than view and data model.",
    )


class TestConsistencyError:
    @pytest.mark.parametrize("model_yaml", list(consistent_models()))
    def test_consistent_models(self, model_yaml: str) -> None:
        """Test that consistent models do not produce consistency errors."""

        # This is not a test of the DMSTableImporter, but it is the most straightforward way to create a
        # RequestSchema from a YAML string. It is assumed that the YAML is valid without syntax errors.
        yaml_file = MagicMock(spec=Path)
        yaml_file.read_text.return_value = model_yaml
        model = DMSTableImporter.from_yaml(yaml_file).to_data_model()

        orchestrator = DmsDataModelRulesOrchestrator(
            cdf_snapshot=SchemaSnapshot(),  # Empty CDF
            limits=SchemaLimits(),
            modus_operandi="additive",
            enable_alpha_validators=True,
        )

        orchestrator.run(model)

        consistency_errors = [issue for issue in orchestrator.issues if isinstance(issue, ConsistencyError)]

        assert not consistency_errors, (
            f"Expected no consistency errors, but found: {[error.message for error in consistency_errors]}"
        )
