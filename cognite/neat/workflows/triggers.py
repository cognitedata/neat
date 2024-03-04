import json
import logging
import threading
import time

import schedule
from fastapi import Request

from cognite.neat.workflows.manager import WorkflowManager
from cognite.neat.workflows.model import FlowMessage, StepType, WorkflowState


class TriggerManager:
    """Triggers are the way to start a workflow. They are defined in the workflow definition file."""

    def __init__(self, workflow_manager: WorkflowManager):
        self.workflow_manager = workflow_manager
        self.is_running = False
        self.thread = None

    def start_workflow_from_http_request(self, workflow_name: str, step_id: str, request: Request, body: bytes):
        logging.info(f"New HTTP trigger request for workflow {workflow_name} step {step_id}")
        headers = dict(request.headers)
        logging.debug(f"Request headers = {headers}")
        json_payload = None
        try:
            json_payload = json.loads(body)
        except Exception as e:
            logging.info(f"Error parsing json body {e}")
        logging.debug(f"Request object = {json_payload}")

        flow_msg = FlowMessage(payload=json_payload, headers=dict(headers))
        start_status = self.workflow_manager.start_workflow_instance(
            workflow_name=workflow_name, step_id=step_id, flow_msg=flow_msg
        )
        if start_status.is_success and start_status.workflow_instance:
            return start_status.workflow_instance.flow_message

    def resume_workflow_from_http_request(
        self, workflow_name: str, step_id: str, instance_id: str, request: Request, body: bytes
    ):
        if instance_id != "default":
            workflow = self.workflow_manager.get_workflow_instance(instance_id)
        else:
            returned = self.workflow_manager.get_workflow(workflow_name)
            if returned is None:
                return {"result": "Workflow instance not found"}
            workflow = returned

        json_payload = None
        try:
            json_payload = json.loads(body)
        except ValueError as e:
            logging.info(f"Error parsing json body {e}")
        flow_msg = FlowMessage(payload=json_payload)
        if workflow.state == WorkflowState.RUNNING_WAITING:
            workflow.resume_workflow(flow_message=flow_msg, step_id=step_id)
            return {"result": "Workflow instance resumed"}

        return {"result": "Workflow instance not in RUNNING_WAITING state"}

    def _start_scheduler_main_loop(self):
        """Starts a scheduler main loop for the workflows

        Parameters
        ----------

        """
        logging.info("Starting scheduler main loop")
        self.is_running = True

        def main_loop():
            while self.is_running:
                schedule.run_pending()
                time.sleep(1)
            logging.info("Scheduler main loop stopped")

        self.thread = threading.Thread(target=main_loop)
        self.thread.start()

    def stop_scheduler_main_loop(self):
        """Stops a scheduler main loop for the workflows

        Parameters
        ----------

        """
        logging.info("Stopping scheduler main loop")
        self.is_running = False
        if self.thread:
            self.thread.join()
        logging.info("Scheduler main loop stopped")

    def every_weekday_schedule(self, weekday_str: str):
        return getattr(schedule.every(), weekday_str)

    def start_time_schedulers(self):
        """Starts a time scheduler for the workflows

        Parameters
        ----------

        """
        logging.info("Starting time trigger scheduler")
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

        trigger_steps_count = 0
        for workflow in self.workflow_manager.workflow_registry.values():
            for step in workflow.workflow_steps:
                if step.trigger and step.stype == StepType.TIME_TRIGGER and step.enabled:
                    # params
                    every_str = step.params["interval"]
                    logging.info(f"Starting time trigger scheduler for {workflow.name} {step.id} {every_str}")
                    every_str = every_str.replace("every", "").strip()

                    if "at" in every_str:  # "day at 10:30:00"
                        every = every_str.split("at ")
                        if len(every) == 2:
                            interval_unit = every[0]
                            interval_value = every[1]
                            if "day" in interval_unit:
                                if interval_unit.lower() in weekdays:
                                    trigger_steps_count += 1
                                    self.every_weekday_schedule(interval_unit.lower()).at(interval_value).do(
                                        workflow.start, start_step_id=step.id
                                    )
                                else:
                                    trigger_steps_count += 1
                                    schedule.every().day.at(interval_value).do(workflow.start, start_step_id=step.id)
                        else:
                            logging.error(f"Invalid time trigger interval {every_str}")

                    else:  # "5 minutes"
                        every = every_str.split(" ")
                        if len(every) == 2:
                            interval_unit = every[1]
                            interval_value = every[0]
                            trigger_steps_count += 1
                            if "minutes" in interval_unit:  # "day at 10:30:00" , "5 minutes"
                                schedule.every(int(interval_value)).minutes.do(workflow.start, start_step_id=step.id)
                            elif "hours" in interval_unit:
                                schedule.every(int(interval_value)).hours.do(workflow.start, start_step_id=step.id)
                            elif "days" in interval_unit:
                                schedule.every(int(interval_value)).days.do(workflow.start, start_step_id=step.id)
                            elif "seconds" in interval_unit:
                                schedule.every(int(interval_value)).seconds.do(workflow.start, start_step_id=step.id)
                            else:
                                logging.error(f"Invalid time trigger interval {every_str}")
                                trigger_steps_count -= 1
                        else:
                            logging.error(f"Invalid time trigger interval {every_str}")

        if trigger_steps_count > 0 and not self.is_running:
            self._start_scheduler_main_loop()
            logging.info("ALl Time trigger scheduler started")
        else:
            logging.info("No Time trigger scheduler started")

    def reload_all_triggers(self):
        """Reloads all triggers

        Parameters
        ----------
        """
        logging.info("Reloading all triggers")
        schedule.clear()
        self.is_running = False
        time.sleep(1)
        self.start_time_schedulers()
