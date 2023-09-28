from cognite.client import CogniteClient

from cognite.neat.workflows.model import FlowMessage


class WorkflowTaskBuilder:
    """Collection of all base tasks for workflows.All tasks must run in the context of a workflow including threads."""

    def __init__(self, cdf_client: CogniteClient | None, workflow_manager):
        # TODO : figure out circular import and set type to WorkflowManager
        self.cdf_client = cdf_client
        self.workflow_manager = workflow_manager

    def start_workflow_task(self, workflow_name: str, sync: bool, flow_message: FlowMessage | None):
        """Call a workflow task from another workflow"""
        return self.workflow_manager.start_workflow_instance(
            workflow_name=workflow_name, flow_msg=flow_message, sync=sync
        )
