from typing import ClassVar

from cognite.neat._store import NeatGraphStore
from cognite.neat._workflows.model import FlowMessage
from cognite.neat._workflows.steps.data_contracts import (
    MultiRuleData,
    NeatGraph,
)
from cognite.neat._workflows.steps.step_model import Configurable, Step

__all__ = ["GraphStoreConfiguration"]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class GraphStoreConfiguration(Step):
    """
    This step initializes source OR solution graph store
    """

    description = "This step initializes the source and solution graph stores."
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Graph store type",
            value="oxigraph",
            label="Graph store type, supported: oxigraph, rdflib",
            options=["oxigraph", "rdflib"],
        ),
    ]

    def run(  # type: ignore[override]
        self, rules_data: MultiRuleData | None = None
    ) -> (FlowMessage, NeatGraph):  # type: ignore[syntax]
        store_type = self.configs.get("Graph store type", "oxigraph")

        if store_type == "oxigraph":
            store = NeatGraph(graph=NeatGraphStore.from_oxi_store(rules=rules_data.information if rules_data else None))
        else:
            store = NeatGraph(
                graph=NeatGraphStore.from_memory_store(rules=rules_data.information if rules_data else None)
            )

        return (
            FlowMessage(output_text="Graph store configured successfully"),
            store,
        )
