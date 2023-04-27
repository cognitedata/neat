from cognite.client import CogniteClient

from cognite.neat.core.workflow.model import FlowMessage


class WorkflowTaskBuilder:
    """Collection of all base tasks for workflows.All tasks must run in the context of a workflow including threads."""

    def __init__(self, cdf_client: CogniteClient, worflow_manager):
        # TODO : figure out ciclura import and set type to WorkflowManager
        self.cdf_client = cdf_client
        self.workflow_manager = worflow_manager

    def start_workflow_task(self, workflow_name: str, sync: bool, flow_message: FlowMessage) -> FlowMessage:
        """Call a workflow task from another workflow"""
        workflow = self.workflow_manager.get_workflow(workflow_name)
        return workflow.start(sync=sync, flow_message=flow_message)
