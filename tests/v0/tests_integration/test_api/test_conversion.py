from pathlib import Path

import pytest
import yaml

from cognite.neat.v0.core._client import NeatClient
from cognite.neat.v0.core._data_model.importers import DictImporter
from cognite.neat.v0.core._data_model.models import PhysicalDataModel
from cognite.neat.v0.core._data_model.transformers import (
    ConceptualToPhysical,
    VerifyConceptualDataModel,
)
from cognite.neat.v0.core._issues import catch_issues
from tests.v0.data import SchemaData


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
        dms_rules: PhysicalDataModel | None = None
        with catch_issues() as issues:
            rules = DictImporter.from_yaml_file(
                conceptual_filepath, source_name=conceptual_filepath.name
            ).to_data_model()
            info_rules = VerifyConceptualDataModel(validate=True, client=neat_client).transform(rules)
            dms_rules = ConceptualToPhysical().transform(info_rules)

        assert not issues
        assert isinstance(dms_rules, PhysicalDataModel)
        assert dms_rules.dump(mode="json", sort=True, exclude_none=True, exclude_unset=True) == yaml.safe_load(
            physical_filepath.read_text()
        )
