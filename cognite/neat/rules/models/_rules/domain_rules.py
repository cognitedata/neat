from .base import CoreMetadata, RoleTypes, RuleModel


class DomainMetadata(CoreMetadata):
    role: RoleTypes = RoleTypes.domain_expert
    creator: str | list[str]


class DomainRules(RuleModel):
    metadata: DomainMetadata
