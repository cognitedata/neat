from typing import TypeAlias

from cognite.neat._graph.extractors import BaseExtractor
from cognite.neat._graph.transformers import BaseTransformer, BaseTransformerStandardised
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.transformers import RulesTransformer

Action: TypeAlias = BaseImporter | BaseExtractor | RulesTransformer | BaseTransformerStandardised | BaseTransformer
