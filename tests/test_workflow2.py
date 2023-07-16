import pytest

from cognite.neat.core.exceptions import InvalidWorkFlowError
from cognite.neat.core.workflow2.base import Step
from cognite.neat.core.workflow2.data import PathData
from cognite.neat.core.workflow2.manager import Manager
from cognite.neat.core.workflow2.workflows.sheet2cdf import sheet_to_cdf
from tests.config import constants


class SetPath(Step):
    def run(self) -> PathData:
        return PathData(excel_file_path=constants.SIMPLE_TRANSFORMATION_RULES)


def test_run_sheet_to_cdf_workflow():
    # Arrange
    full_workflow = [SetPath()] + sheet_to_cdf
    manager = Manager()
    assert not manager.data, "Manager should be empty"

    # Act
    with pytest.raises(InvalidWorkFlowError) as e:
        manager.run_workflow(full_workflow)

    # Assert
    assert e.value.message == "In the workflow step CreateCDFLabels the following data is missing: ['ClientData']."
