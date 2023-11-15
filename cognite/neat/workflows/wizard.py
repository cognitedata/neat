from pathlib import Path
import shutil
from pydantic import BaseModel, Field
from typing import List, Optional, Union

from tests.config import PACKAGE_DIRECTORY


class Option(BaseModel):
    label: str
    value: str
    nextStep: Optional[str] = None
    workflowSteps: Optional[Union[List[str], str]] = None


class Answer(BaseModel):
    values: dict[str, str]
    label: str


class Step(BaseModel):
    id: str
    question: str
    description: str
    options: List[Option]
    defaultNextStep: str
    type: str
    answer: Answer | None = None
    img: Optional[str] = None
    workflowTemplate: Optional[str] = None
    action: Optional[str] = None


class Wizard(BaseModel):
    name: str
    steps: List[Step]


class WizardProcessor:
    @classmethod
    def from_json(cls, json: dict, data_store_path: Path):
        return cls(Wizard.parse_obj(json), data_store_path)

    def __init__(self, wizard: Wizard, data_store_path: Path):
        self.wizard = wizard
        self.data_store_path = data_store_path

    def copy_workflow_from_template(self, answers: dict):
        # filter workflow step that has workflow_template
        template_step = self.get_step_by_action("save_workflow")

        if template_step is None:
            return None

        workflow_template_name = template_step.workflowTemplate
        WORKFLOW_TEMPLATES_PATH = PACKAGE_DIRECTORY / "workflows" / "templates"

        new_workflow_name = template_step.answer.values["workflow_name"]
        new_workflow_description = template_step.answer.values["workflow_description"]

        ## copy workflow template to workflow store
        workflow_template_path = WORKFLOW_TEMPLATES_PATH / workflow_template_name
        workflow_store_path = self.data_store_path / "workflows" / new_workflow_name
        workflow_store_path.mkdir(parents=True, exist_ok=True)
        shutil.copytree(workflow_template_path, workflow_store_path)

        ## copy workflow folder to workflow store

        return

    def replace_template_step(self, steps: List[Step]):
        # step in template should be replaced with one or several steps from listed in step document. Steps matched by step ID
        self.wizard.steps = steps

    def get_step_by_id(self, step_id: str):
        return next((step for step in self.wizard.steps if step.id == step_id), None)

    def get_step_by_action(self, action: str):
        return next((step for step in self.wizard.steps if step.action == action), None)
