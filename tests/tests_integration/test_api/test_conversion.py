from pathlib import Path

import pytest
import yaml

from cognite.neat.core._client import NeatClient
from cognite.neat.core._issues import catch_issues
from cognite.neat.core._rules.importers import YAMLImporter
from cognite.neat.core._rules.models import DMSRules
from cognite.neat.core._rules.transformers import (
    InformationToDMS,
    VerifyInformationRules,
)
from tests.data import SchemaData


class TestValidate:
    @pytest.mark.parametrize(
        "conceptual_filepath, physical_filepath",
        [
            pytest.param(conceptual, physical, id=conceptual.stem)
            for conceptual, physical in SchemaData.Conversion.iterate()
        ],
    )
    def test_convert_conceptual_rules(
        self, conceptual_filepath: Path, physical_filepath: Path, neat_client: NeatClient
    ) -> None:
        dms_rules: DMSRules | None = None
        with catch_issues() as issues:
            rules = YAMLImporter.from_file(conceptual_filepath, source_name=conceptual_filepath.name).to_rules()
            info_rules = VerifyInformationRules(validate=True, client=neat_client).transform(rules)
            dms_rules = InformationToDMS().transform(info_rules)

        assert not issues
        assert isinstance(dms_rules, DMSRules)
        assert dms_rules.dump(mode="json", sort=True, exclude_none=True, exclude_unset=True) == yaml.safe_load(
            physical_filepath.read_text()
        )
