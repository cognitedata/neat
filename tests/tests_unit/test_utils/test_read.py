import pytest

from cognite.neat.core._issues.errors import NeatValueError
from cognite.neat.core._utils.read import read_conceptual_model
from tests.data import SchemaData


class TestReadConceptualModel:
    def test_read_conceptual_model(self) -> None:
        model = read_conceptual_model(SchemaData.Conceptual.info_arch_car_rules_xlsx)

        assert model is not None

    def test_dms_model_raises(self) -> None:
        with pytest.raises(NeatValueError):
            read_conceptual_model(SchemaData.Physical.car_dms_rules_xlsx)
