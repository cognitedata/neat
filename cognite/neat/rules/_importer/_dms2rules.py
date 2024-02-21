from cognite.neat.rules.models._rules import DMSRules, DMSSchema

from ._base import BaseImporter


class DMSImporter(BaseImporter):
    def __init__(self, schema: DMSSchema):
        self.schema = schema

    def to_rules(self) -> DMSRules:
        raise NotImplementedError
