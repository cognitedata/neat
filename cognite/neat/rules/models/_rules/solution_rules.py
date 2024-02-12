from datetime import datetime
from typing import ClassVar

from cognite.neat.rules.models._rules.information_rules import InformationArchitectMetadata

from .base import BaseRules, ExternalId, RoleTypes, Space
from .domain_rules import DomainMetadata


class AssetSolutionArchitectMetadata(InformationArchitectMetadata):
    ...


class DmsSolutionArchitectMetadata(DomainMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.cdf_solution_architect
    space: Space
    externalId: ExternalId
    version: str
    contributor: str | list[str]
    created: datetime
    updated: datetime

    @classmethod
    def from_information_architect_metadata(
        cls, metadata: InformationArchitectMetadata, space: str | None = None, externalId: str | None = None
    ):
        metadata_as_dict = metadata.model_dump()
        metadata_as_dict["space"] = space or "neat-playground"
        metadata_as_dict["externalId"] = externalId or "neat_model"
        return cls(**metadata_as_dict)

    @classmethod
    def from_domain_expert_metadata(
        cls,
        metadata: DomainMetadata,
        space: str | None = None,
        externalId: str | None = None,
        version: str | None = None,
        contributor: str | list[str] | None = None,
        created: datetime | None = None,
        updated: datetime | None = None,
    ):
        metadata_as_dict = metadata.model_dump()
        metadata_as_dict["space"] = space or "neat-playground"
        metadata_as_dict["externalId"] = externalId or "neat_model"
        metadata_as_dict["version"] = version or "0.1.0"
        metadata_as_dict["contributor"] = contributor or "Cognite"
        metadata_as_dict["created"] = created or datetime.utcnow()
        metadata_as_dict["updated"] = updated or datetime.utcnow()

        return cls(**metadata_as_dict)


class AssetRules(BaseRules):
    metadata: AssetSolutionArchitectMetadata


class DMSRules(BaseRules):
    metadata: DmsSolutionArchitectMetadata
