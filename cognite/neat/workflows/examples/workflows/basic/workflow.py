import logging

from cognite.client import CogniteClient

from cognite.neat.core.workflow.base import BaseWorkflow
from cognite.neat.core.workflow.model import FlowMessage


class BasicNeatWorkflow(BaseWorkflow):
    def __init__(self, name: str, client: CogniteClient):
        super().__init__(name, client, [])
        self.counter = 0
        self.metrics.register_metric("counter_1", "", "counter", ["step"])
        self.metrics.register_metric("gauge_1", "", "gauge", ["step"])

    def step_run_experiment_1(self, flow_msg: FlowMessage = None):
        logging.info("Running experiment 1")
        logging.info("Done running experiment 4444")
        self.counter = self.counter + 1
        logging.info("Counter: " + str(self.counter))

        self.metrics.get("counter_1", {"step": "run_experiment_1"}).inc()
        self.metrics.get("gauge_1", {"step": "run_experiment_1"}).set(self.counter)

        if self.counter > 5:
            return FlowMessage(output_text="Done running experiment", next_step_ids=["error_handler"])
        else:
            return FlowMessage(
                output_text=f"Running iteration {self.counter} of xperiment", next_step_ids=["run_experiment_1"]
            )

    def step_cleanup(self, flow_msg: FlowMessage = None):
        logging.info("Cleanup")

    def step_error_handler(self, flow_msg: FlowMessage = None):
        logging.info("Error handler")
        return FlowMessage(output_text="Error handleed")
