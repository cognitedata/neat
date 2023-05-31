import json
import logging
import threading
import time

import schedule
from fastapi import Depends, FastAPI, Request

from cognite.neat.core.workflow.manager import WorkflowManager
from cognite.neat.core.workflow.model import FlowMessage, StepType, WorkflowState


async def get_body(request: Request):
    return await request.body()


fast_api_depends = Depends(get_body)


class TriggerManager:
    """Triggers are the way to start a workflow. They are defined in the workflow definition file."""

    def __init__(self, workflow_manager: WorkflowManager):
        self.workflow_manager = workflow_manager
        self.is_running = False
        self.thread = None

    def start_http_listeners(self, web_server: FastAPI):
        """Starts a HTTP listener for the workflows

        Parameters
        ----------
        web_server : FastAPI instance
        """
        logging.info("Starting HTTP trigger endpoint")

        @web_server.post("/api/workflow/{workflow_name}/http_trigger/{step_id}")
        def start_workflow(workflow_name: str, step_id: str, request: Request, body: bytes = fast_api_depends):
            logging.info(f"New HTTP trigger request for workflow {workflow_name} step {step_id}")
            workflow = self.workflow_manager.get_workflow(workflow_name)
            json_payload = None
            try:
                # TODO: Add support for other content types
                json_payload = json.loads(body)
            except Exception as e:
                logging.info(f"Error parsing json body {e}")
            logging.debug(f"Request object = {json_payload}")

            flow_msg = FlowMessage(payload=json_payload)
            sync = bool(request.headers.get("Neat-Sync-Response", True))
            max_wait_time = int(request.headers.get("Neat-Sync-Max-Wait", 30))
            logging.info(f"Workflow {workflow_name} state = {workflow.state} sync={sync}")
            if workflow.state == WorkflowState.RUNNING_WAITING:
                workflow.resume_workflow(flow_message=flow_msg, step_id=step_id)
                return {"result": "Workflow instance resumed"}
            elif workflow.state != WorkflowState.RUNNING:
                result = workflow.start(sync=sync, flow_message=flow_msg, start_step_id=step_id)
                if result:
                    if result.payload:
                        logging.info(f"Workflow result payload = {result.payload}")
                        return result.payload
            else:
                # wait until workflow transition to RUNNING state and then start , set max wait time to 10 seconds
                start_time = time.perf_counter()
                # wait until workflow transition to RUNNING state and then start , set max wait time to 10 seconds. The operation is executed in callers thread 
                logging.info("Existing workflow instance already running , waiting for RUNNING state")
                while workflow.state == WorkflowState.RUNNING:
                    elapsed_time = time.perf_counter() - start_time
                    if elapsed_time > max_wait_time:
                        logging.info(f"Workflow {workflow_name} wait time exceeded . elapsed time = {elapsed_time}, max wait time = {max_wait_time}")
                        return {"result": "Workflow instance already running.Wait time exceeded"}
                    time.sleep(0.5)
                result = workflow.start(sync=sync, flow_message=flow_msg, start_step_id=step_id)
                if result:
                    if result.payload:
                        logging.info(f"Workflow result payload = {result.payload}")
                        return result.payload
                logging.info(f"Workflow {workflow_name} is already running")
                return {"result": "Workflow instance already running"}
            
            return {"result": "Workflow instance started"}

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

    def start_time_schedulers(self):
        """Starts a time scheduler for the workflows

        Parameters
        ----------

        """
        logging.info("Starting time trigger scheduler")

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

    