from pydantic import BaseModel, ConfigDict, Field

from cognite.neat._data_model.deployer.data_classes import FieldChange
from cognite.neat._data_model.models.dms import SchemaResourceId


class FixAction(BaseModel):
    """An atomic, individually-applicable fix for a schema issue.

    Attributes:
        resource_id: Reference to the resource being modified.
        changes: List of field-level changes.
        message: Human-readable description of what this fix does.
        code: The validator code (e.g., "NEAT-DMS-PERFORMANCE-001") for grouping in UI.
    """

    model_config = ConfigDict(frozen=True)

    resource_id: SchemaResourceId
    changes: tuple[FieldChange, ...] = Field(default_factory=tuple)
    message: str | None = None
    code: str
