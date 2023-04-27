import logging
import threading
import time

import schedule
from fastapi import FastAPI

from cognite.neat.core.workflow.manager import WorkflowManager
from cognite.neat.core.workflow.model import StepType
from cognite.neat.explorer.data_classes.rest import RunWorkflowRequest


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

        @web_server.post("/api/workflow/http_trigger")
        def start_workflow(request: RunWorkflowRequest):
            logging.info("Starting workflow endpoint")
            workflow = self.workflow_manager.get_workflow(request.name)
            result = workflow.start()
            return {"result": result}

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
