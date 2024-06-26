from cognite.neat.rules.models import AssetRules

from ._information_rules import _SharedAnalysis


class AssetArchitectRulesAnalysis(_SharedAnalysis):
    """Assumes analysis over only the complete schema"""

    def __init__(self, rules: AssetRules):
        self.rules = rules
