from dataclasses import dataclass
from typing import Any

from cognite.client.data_classes.data_modeling import ContainerId, ViewId

from ._spreadsheet import InvalidPropertySpecification


@dataclass(frozen=True)
class ReferenceNonExistingContainer(InvalidPropertySpecification):
    description = "The container referenced by the property is missing in the container sheet"
    fix = "Add the container to the container sheet"

    container_id: ContainerId

    def message(self) -> str:
        return (
            f"In {self.sheet_name}, row={self.row}, column={self.column}: The container with "
            f"id {self.container_id} is missing in the container sheet."
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["container_id"] = self.container_id
        return output


@dataclass(frozen=True)
class ReferencedNonExistingView(InvalidPropertySpecification):
    description = "The view referenced by the property is missing in the view sheet"
    fix = "Add the view to the view sheet"

    view_id: ViewId

    def message(self) -> str:
        return (
            f"In {self.sheet_name}, row={self.row}, column={self.column}: The view with "
            f"id {self.view_id} is missing in the view sheet."
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view_id"] = self.view_id
        return output
