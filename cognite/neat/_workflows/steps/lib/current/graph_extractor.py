import json
from pathlib import Path
from typing import ClassVar, cast

from cognite.neat._graph.extractors import RdfFileExtractor
from cognite.neat._graph.extractors._mock_graph_generator import MockGraphGenerator
from cognite.neat._issues.errors import WorkflowStepNotInitializedError
from cognite.neat._rules._shared import DMSRules, InformationRules
from cognite.neat._workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat._workflows.steps.data_contracts import MultiRuleData, NeatGraph
from cognite.neat._workflows.steps.step_model import Configurable, Step

__all__ = ["GraphFromRdfFile", "GraphFromMockData"]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class GraphFromMockData(Step):
    """
    This step generate mock graph based on the defined classes and target number of instances
    """

    description = "This step generate mock graph based on the defined classes and target number of instances"
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Class count",
            value="",
            label="Target number of instances for each class",
        ),
        Configurable(
            name="Graph",
            value="solution",
            label="The name of target graph.",
            options=["source", "solution"],
        ),
    ]

    def run(  # type: ignore[override, syntax]
        self, rules: MultiRuleData, store: NeatGraph
    ) -> FlowMessage:
        if self.configs is None:
            raise WorkflowStepNotInitializedError(type(self).__name__)

        if not rules.information and not rules.dms:
            return FlowMessage(
                error_text="Rules must be made either by Information Architect or DMS Architect!",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        try:
            class_count = json.loads(self.configs["Class count"]) if self.configs["Class count"] else {}
        except Exception:
            return FlowMessage(
                error_text="Defected JSON stored in class_count",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        extractor = MockGraphGenerator(
            cast(InformationRules | DMSRules, rules.information or rules.dms),
            class_count,
        )

        store.graph.write(extractor)

        return FlowMessage(output_text=f"Instances loaded to the {store.__class__.__name__}")


class GraphFromRdfFile(Step):
    """
    This step extract instances from a file into the source graph. The file must be in RDF format.
    """

    description = "This step extract instances from a file into the source graph. The file must be in RDF format."
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="File path",
            value="source-graphs/source-graph-dump.xml",
            label="File name of source graph data dump in RDF format",
        )
    ]

    def run(self, store: NeatGraph) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise WorkflowStepNotInitializedError(type(self).__name__)

        if source_file := self.configs["File path"]:
            store.graph.write(
                RdfFileExtractor(  # type: ignore[abstract]
                    filepath=self.data_store_path / Path(source_file),
                )
            )

        else:
            raise ValueError("You need a valid file path to be specified")

        return FlowMessage(output_text="Instances loaded to NeatGraph!")
