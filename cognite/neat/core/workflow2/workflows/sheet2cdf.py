from cognite.neat.core.workflow2 import steps
from cognite.neat.core.workflow2.base import Step

sheet_to_cdf: list[Step] = [
    steps.LoadTransformationRules(),
    steps.ConfiguringStores(),
    steps.LoadInstancesToGraph(),
    steps.CreateCDFLabels(),
]
