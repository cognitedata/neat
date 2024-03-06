import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import ClassVar, cast

import yaml
from cognite.client import CogniteClient
from prometheus_client import Gauge
from rdflib import Namespace

from cognite.neat.rules import exporter, importer, importers
from cognite.neat.rules.models._rules import RoleTypes
from cognite.neat.rules.models._rules._types import DataModelEntity, Undefined
from cognite.neat.rules.models.rdfpath import TransformationRuleType
from cognite.neat.rules.models.rules import Class, Classes, Metadata, Properties, Property, Rules
from cognite.neat.rules.models.value_types import ValueType
from cognite.neat.rules.validation.formatters import FORMATTER_BY_NAME
from cognite.neat.utils.utils import generate_exception_report
from cognite.neat.workflows import utils
from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.cdf_store import CdfStore
from cognite.neat.workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat.workflows.steps.data_contracts import MultiRuleData, RulesData, SolutionGraph, SourceGraph
from cognite.neat.workflows.steps.step_model import Configurable, Step

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()

__all__ = [
    "ImportExcelToRules",
    "ImportOpenApiToRules",
    "ImportArbitraryJsonYamlToRules",
    "ImportGraphToRules",
    "ImportOntologyToRules",
    "ImportExcelValidator",
    "ImportFromDataModelStorage",
]


class ImportExcelToRules(Step):
    """
    This step import rules from the Excel file
    """

    description = "This step import rules from the Excel file"
    version = "private-alpha"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="validation_report_storage_dir",
            value="rules_validation_report",
            label="Directory to store validation report",
        ),
        Configurable(
            name="validation_report_file",
            value="rules_validation_report.txt",
            label="File name to store validation report",
        ),
        Configurable(
            name="file_name",
            value="rules.xlsx",
            label="Full name of the rules file in rules folder. If includes path, \
                it will be relative to the neat data folder",
        ),
        Configurable(name="version", value="", label="Optional version of the rules file"),
    ]

    def run(self, cdf_store: CdfStore) -> (FlowMessage, RulesData):  # type: ignore[syntax, override]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)
        store = cdf_store
        # rules file
        if self.configs is None:
            raise ValueError(f"Step {type(self).__name__} has not been configured.")
        rules_file = Path(self.configs["file_name"])
        if str(rules_file.parent) == ".":
            rules_file_path = Path(self.data_store_path) / "rules" / rules_file
        else:
            rules_file_path = Path(self.data_store_path) / rules_file

        version = self.configs["version"]

        # rules validation
        report_file = self.configs["validation_report_file"]
        report_dir_str = self.configs["validation_report_storage_dir"]
        report_dir = self.data_store_path / Path(report_dir_str)
        report_dir.mkdir(parents=True, exist_ok=True)
        report_full_path = report_dir / report_file

        if not rules_file_path.exists():
            logging.info(f"Rules files doesn't exist in local fs {rules_file_path}")

        if rules_file_path.exists() and not version:
            logging.info(f"Loading rules from {rules_file_path}")
        elif rules_file_path.exists() and version:
            hash = utils.get_file_hash(rules_file_path)
            if hash != version:
                store.load_rules_file_from_cdf(str(rules_file), version)
        else:
            store.load_rules_file_from_cdf(str(rules_file), version)

        raw_rules = importer.ExcelImporter(rules_file_path).to_raw_rules()
        rules, errors, _ = raw_rules.to_rules(return_report=True, skip_validation=False)
        report = "# RULES VALIDATION REPORT\n\n" + generate_exception_report(errors, "Errors")

        report_full_path.write_text(report)

        text_for_report = (
            "<p></p>"
            "Download rules validation report "
            f'<a href="/data/{report_dir_str}/{report_file}?{time.time()}" '
            f'target="_blank">here</a>'
        )

        if rules is None:
            return FlowMessage(
                error_text=f"Failed to load transformation rules! {text_for_report}",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        if self.metrics is None:
            raise ValueError(f"Step {type(self).__name__} has not been configured.")
        rules_metrics = cast(
            Gauge,
            self.metrics.register_metric(
                "data_model_rules", "Transformation rules stats", m_type="gauge", metric_labels=["component"]
            ),
        )
        rules_metrics.labels({"component": "classes"}).set(len(rules.classes))
        rules_metrics.labels({"component": "properties"}).set(len(rules.properties))
        logging.info(f"Loaded prefixes {rules.prefixes!s} rules from {rules_file_path.name!r}.")
        output_text = f"<p></p>Loaded {len(rules.properties)} rules! {text_for_report}"

        return FlowMessage(output_text=output_text), RulesData(rules=rules)


class ImportOntologyToRules(Step):
    """The step extracts schema from OpenApi/Swagger specification and generates NEAT transformation rules object."""

    description = "The step extracts NEAT rules object from OWL Ontology and \
        exports them as an Excel rules files for further editing."
    category = CATEGORY
    version = "private-alpha"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="ontology_file_path", value="staging/ontology.ttl", label="Relative path to the OWL ontology file."
        ),
        Configurable(
            name="excel_file_path", value="staging/rules.xlsx", label="Relative path for the Excel rules storage."
        ),
        Configurable(
            name="make_compliant",
            value="True",
            label="Relative path for the Excel rules storage.",
            options=["True", "False"],
        ),
    ]

    def run(self) -> FlowMessage:  # type: ignore[override, syntax]
        ontology_file_path = self.data_store_path / Path(self.configs["ontology_file_path"])
        excel_file_path = self.data_store_path / Path(self.configs["excel_file_path"])
        report_file_path = excel_file_path.parent / f"report_{excel_file_path.stem}.txt"

        make_compliant = self.configs["make_compliant"] == "True"
        try:
            rules = importer.OWLImporter(ontology_file_path).to_rules(make_compliant=make_compliant)
        except Exception:
            rules = importer.OWLImporter(ontology_file_path).to_rules(
                skip_validation=True, make_compliant=make_compliant
            )
        assert isinstance(rules, Rules)
        exporter.ExcelExporter.from_rules(rules).export_to_file(excel_file_path)

        if report := importer.ExcelImporter(filepath=excel_file_path).to_raw_rules().validate_rules():
            report_file_path.write_text(report)

        relative_excel_file_path = str(excel_file_path).split("/data/")[1]
        relative_report_file_path = str(report_file_path).split("/data/")[1]

        output_text = (
            "<p></p>"
            "Rules imported from OWL Ontology can be downloaded here : "
            f'<a href="/data/{relative_excel_file_path}?{time.time()}" '
            f'target="_blank">{excel_file_path.stem}.xlsx</a>'
            "<p></p>"
            "Report can be downloaded here : "
            f'<a href="/data/{relative_report_file_path}?{time.time()}" '
            f'target="_blank">{report_file_path.stem}.txt</a>'
        )

        return FlowMessage(output_text=output_text)


class ImportOpenApiToRules(Step):
    """The step extracts schema from OpenApi/Swagger specification and generates NEAT transformation rules object."""

    description = "The step extracts schema from OpenAPI specification and generates NEAT transformation rules object. \
    The rules object can be serialized to excel file or used directly in other steps."
    category = CATEGORY
    version = "private-alpha"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="openapi_spec_file_path",
            value="workflows/openapi_to_rules/source_data/openapi.json",
            label="Relative path to the OpenAPI spec file.The file can be in either json or in yaml format.",
        ),
        Configurable(
            name="fdm_compatibility_mode",
            value="True",
            label="If set to True, the step will try to convert property names to FDM compatible names.",
            options=["True", "False"],
        ),
    ]

    def run(self) -> (FlowMessage, RulesData):  # type: ignore[override, syntax]
        openapi_file_path = self.data_store_path / Path(self.configs["openapi_spec_file_path"])
        self.processed_classes_counter = 0
        self.processed_properties_counter = 0
        self.failed_classes_counter = 0
        self.failed_properties_counter = 0
        self.failed_classes: dict[str, str] = {}
        self.failed_properties: dict[str, str] = {}
        self.is_fdm_compatibility_mode = self.configs["fdm_compatibility_mode"] == "True"
        rules = self.open_api_to_rules(openapi_file_path)
        report = f" Generated Rules and source data model from OpenApi specs   \
        <p> Processed {self.processed_classes_counter} classes \
        and {self.processed_properties_counter} properties. </p> \
        <p> Failed to process {self.failed_classes_counter} classes and \
        {self.failed_properties_counter} properties. </p>"
        report_obj = {
            "processed_classes_counter": self.processed_classes_counter,
            "processed_properies_counter": self.processed_properties_counter,
            "failed_classes": self.failed_classes,
            "failed_properties": self.failed_properties,
        }
        return (FlowMessage(output_text=report, payload=report_obj), RulesData(rules=rules))

    def open_api_to_rules(self, open_api_spec_file_path: Path) -> Rules:
        """Converts OpenAPI spec to NEAT transformation rules object."""
        with open_api_spec_file_path.open("r") as openapi_file:
            if open_api_spec_file_path.suffix == ".json":
                openapi_spec = json.load(openapi_file)
            elif open_api_spec_file_path.suffix == ".yaml":
                openapi_spec = yaml.safe_load(openapi_file)

        metadata = Metadata(
            title="OpenAPI to DM transformation rules",
            description="OpenAPI to DM transformation rules",
            version="0.1",
            creator="Cognite",
            created=datetime.utcnow(),
            namespace=Namespace("http://purl.org/cognite/neat#"),
            prefix="neat",
            suffix="OpenAPI",
        )

        classes = Classes()
        properties = Properties()

        # Loop through OpenAPI components
        for component_name, component_info in openapi_spec.get("components", {}).get("schemas", {}).items():
            if self.is_fdm_compatibility_mode:
                class_name = get_dms_compatible_name(create_fdm_compatibility_class_name(component_name))
            else:
                class_name = component_name
            class_id = class_name
            logging.info(f" OpenAPi parser : Processing class {class_id} ")
            try:
                class_ = Class(
                    class_id=class_id,
                    class_name=class_name,
                    description=component_info.get("description", component_info.get("title", "empty")),
                )
                classes[class_id] = class_
                self.processed_classes_counter += 1
                # Loop through properties of OpenApi spec]
                self.process_properies(properties, class_id, class_name, component_info)

            except Exception as e:
                logging.error(f" OpenAPi parser : Error creating class {class_id}: {e}")
                self.failed_classes_counter += 1
                self.failed_classes[class_id] = str(e)

        rules = Rules(metadata=metadata, classes=classes, properties=properties, prefixes={}, instances=[])

        return rules

    def process_properies(
        self,
        rules_properties: Properties,
        class_id: str,
        class_name: str,
        component: dict,
        parent_property_name: str | None = None,
    ):
        # component can have keys : type, description, properties, required, title, allOf, anyOf, oneOf§
        logging.info(f" OpenAPi parser : Processing properties for class {class_id} , component {component}")
        for component_name, component_info in component.items():
            if component_name == "allOf" or component_name == "anyOf" or component_name == "oneOf":
                for sub_component in component_info:
                    self.process_properies(rules_properties, class_id, class_name, sub_component, component_name)
            elif component_name == "properties":
                for prop_name, prop_info in component_info.items():
                    prop_id = prop_name
                    if prop_name == "allOf" or prop_name == "anyOf" or prop_name == "oneOf":
                        if isinstance(prop_info, list):
                            prop_type = prop_info[0].get("type", "string")
                        else:
                            logging.error(f" !!!!! prop info is not a list . its: {prop_info} ")

                    else:
                        prop_type = prop_info.get("type", "string")
                        if prop_type == "array":
                            self.process_properies(
                                rules_properties, class_id, class_name, prop_info.get("items", {}), prop_name
                            )
                            continue
                    expected_value_type = self.map_open_api_type(prop_type)
                    if prop_name == "$ref":
                        ref_class = self.get_ref_class_name(prop_info.get("$ref", ""))
                        expected_value_type = ref_class
                    try:
                        prop = Property(
                            class_id=class_id,
                            property_id=get_dms_compatible_name(prop_id) if self.is_fdm_compatibility_mode else prop_id,
                            property_name=(
                                get_dms_compatible_name(prop_name) if self.is_fdm_compatibility_mode else prop_name
                            ),
                            property_type="ObjectProperty",
                            description=prop_info.get("description", prop_info.get("title", "empty")),
                            expected_value_type=ValueType(prefix="neat", suffix=expected_value_type),
                            cdf_resource_type=["Asset"],
                            resource_type_property="Asset",  # type: ignore
                            rule_type=TransformationRuleType("rdfpath"),
                            rule=f"neat:{class_name}(neat:{prop_name})",
                            label="linked to",
                        )
                        self.processed_properties_counter += 1
                        rules_properties[class_id + prop_id] = prop
                    except Exception as e:
                        logging.error(f" OpenAPi parser : Error creating property {prop_id}: {e}")
                        self.failed_properties_counter += 1
                        self.failed_properties[prop_id] = str(e)
            elif component_name == "$ref":
                ref_class = self.get_ref_class_name(component_info)
                if parent_property_name is not None:
                    prop = Property(
                        class_id=class_id,
                        property_id=parent_property_name,
                        property_name=parent_property_name,
                        property_type="ObjectProperty",
                        description="no",
                        expected_value_type=ValueType(prefix="neat", suffix=ref_class),
                        cdf_resource_type=["Asset"],
                        resource_type_property="Asset",  # type: ignore
                        rule_type=TransformationRuleType("rdfpath"),
                        rule=f"neat:{class_name}(neat:{parent_property_name})",
                        label="linked to",
                    )
                    rules_properties[class_id + parent_property_name] = prop

    def get_ref_class_name(self, ref: str) -> str:
        ref_payload = ref.split("/")[-1]
        if self.is_fdm_compatibility_mode:
            return get_dms_compatible_name(create_fdm_compatibility_class_name(ref_payload))
        return ref_payload

    def map_open_api_type(self, openapi_type: str) -> str:
        """Map OpenAPI type to NEAT compatible types"""
        if openapi_type == "object":
            datatype = "json"
        elif openapi_type == "array":
            datatype = "sequence"
        elif openapi_type == "number":
            datatype = "float"
        else:
            return openapi_type  # Default to string
        return datatype


class ImportArbitraryJsonYamlToRules(Step):
    """The step extracts schema from arbitrary json or yaml file and generates NEAT transformation rules object."""

    description = "The step extracts schema from arbitrary json file and generates NEAT transformation rules object."
    category = CATEGORY
    version = "private-alpha"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="file_path",
            value="workflows/openapi_to_rules/data/data.json",
            label="Relative path to the json file.The file can be in either json or in yaml format.",
        ),
        Configurable(
            name="fdm_compatibility_mode",
            value="True",
            label="If set to True, the step will try to convert property names to FDM compatible names.",
            options=["True", "False"],
        ),
    ]

    def run(self) -> (FlowMessage, RulesData):  # type: ignore[override, syntax]
        openapi_file_path = Path(self.data_store_path) / Path(self.configs["file_path"])
        self.processed_classes_counter = 0
        self.processed_properies_counter = 0
        self.failed_classes_counter = 0
        self.failed_properties_counter = 0
        self.failed_classes: dict[str, str] = {}
        self.failed_properties: dict[str, str] = {}
        self.is_fdm_compatibility_mode = self.configs["fdm_compatibility_mode"] == "True"

        rules = self.dict_to_rules(openapi_file_path)
        report = f" Generated Rules and source data model from json/yaml   \
        <p> Processed {self.processed_classes_counter} classes and {self.processed_properies_counter} properties. </p> \
        <p> Failed to process {self.failed_classes_counter} classes \
        and {self.failed_properties_counter} properties. </p>"
        report_obj = {
            "processed_classes_counter": self.processed_classes_counter,
            "processed_properies_counter": self.processed_properies_counter,
            "failed_classes": self.failed_classes,
            "failed_properties": self.failed_properties,
        }
        return FlowMessage(output_text=report, payload=report_obj), RulesData(rules=rules)

    def dict_to_rules(self, open_api_spec_file_path: Path) -> Rules:
        """Converts OpenAPI spec to NEAT transformation rules object."""
        with open_api_spec_file_path.open("r") as openapi_file:
            if open_api_spec_file_path.suffix == ".json":
                src_data_obj = json.load(openapi_file)
            elif open_api_spec_file_path.suffix == ".yaml":
                src_data_obj = yaml.safe_load(openapi_file)

        metadata = Metadata(
            title="OpenAPI to DM transformation rules",
            description="OpenAPI to DM transformation rules",
            version="0.1",
            creator="Cognite",
            created=datetime.utcnow(),
            namespace=Namespace("http://purl.org/cognite/neat#"),
            prefix="neat",
            suffix="OpenAPI",
        )

        self.classes = Classes()
        self.properties = Properties()

        self.convert_dict_to_classes_and_props(src_data_obj, None)
        rules = Rules(metadata=metadata, classes=self.classes, properties=self.properties, prefixes={}, instances=[])

        return rules

    def add_class(self, class_name: str, description: str | None = None, parent_class_name: str | None = None):
        if class_name in self.classes:
            return
        if self.is_fdm_compatibility_mode:
            class_name = get_dms_compatible_name(create_fdm_compatibility_class_name(class_name))
        try:
            class_ = Class(class_id=class_name, class_name=class_name, description=description)
            if parent_class_name:
                self.add_property(class_name, "parent", parent_class_name, None)
            self.classes[class_name] = class_
            self.processed_classes_counter += 1
        except Exception as e:
            logging.error(f" OpenAPi parser : Error creating class {class_name}: {e}")
            self.failed_classes_counter += 1
            self.failed_classes[class_name] = str(e)
        return

    def add_property(self, class_name: str, property_name: str, property_type: str, description: str | None = None):
        if class_name + property_name in self.properties:
            return
        if self.is_fdm_compatibility_mode:
            property_name = get_dms_compatible_name(property_name)
            class_name = get_dms_compatible_name(create_fdm_compatibility_class_name(class_name))
        try:
            prop = Property(
                class_id=class_name,
                property_id=property_name,
                property_name=property_name,
                property_type="ObjectProperty",
                description=description,
                expected_value_type=ValueType(prefix="neat", suffix=property_type),
                cdf_resource_type=["Asset"],
                resource_type_property="Asset",  # type: ignore
                rule_type=TransformationRuleType("rdfpath"),
                rule=f"neat:{class_name}(neat:{property_name})",
                label="linked to",
            )
            self.properties[class_name + property_name] = prop
            self.processed_properies_counter += 1
        except Exception as e:
            logging.error(f" OpenAPi parser : Error creating property {property_name}: {e}")
            self.failed_properties_counter += 1
            self.failed_properties[class_name + property_name] = str(e)
        return

    # Iterate through the JSON data and convert it to triples
    def convert_dict_to_classes_and_props(self, data: dict, parent_property_name=None, grand_parent_property_name=None):
        if isinstance(data, dict):
            if len(data) == 0:
                return
            if parent_property_name is None:
                for key, value in data.items():
                    self.convert_dict_to_classes_and_props(value, key)
            else:
                description = None
                self.add_class(parent_property_name, description, grand_parent_property_name)
                for key, value in data.items():
                    self.convert_dict_to_classes_and_props(value, key, parent_property_name)
        elif isinstance(data, list):
            for item in data:
                self.convert_dict_to_classes_and_props(item, parent_property_name, grand_parent_property_name)
        else:
            # Convert scalar values to RDF literals
            data_type = ""
            if isinstance(data, bool):
                data_type = "boolean"
            elif isinstance(data, int):
                data_type = "integer"
            elif isinstance(data, float):
                data_type = "float"
            elif isinstance(data, str):
                data_type = "string"
            else:
                data_type = "string"
            if grand_parent_property_name is None:
                logging.error(" grand_parent_property_name is None")
                return

            self.add_property(grand_parent_property_name, parent_property_name, data_type, None)


def get_dms_compatible_name(name: str) -> str:
    """Converts name to DMS compatible name.It applies both to class and property names"""
    # reserverd words in DMS
    reserved_words_mapping = {
        "space": "src_space",
        "externalId": "external_id",
        "createdTime": "created_time",
        "lastUpdatedTime": "last_updated_time",
        "deletedTime": "deleted_time",
        "edge_id": "src_edge_id",
        "node_id": "src_node_id",
        "project_id": "src_project_id",
        "property_group": "src_property_group",
        "seq": "src_seq",
        "tg_table_name": "src__table_name",
        "extensions": "src_extensions",
    }
    if name in reserved_words_mapping:
        return reserved_words_mapping[name]
    else:
        return name.replace(".", "_")


def create_fdm_compatibility_class_name(input_string: str):
    """Remove underscores and capitalize each word in the string ,
    the conversion is done to improve compliance with DMS naming conventions"""

    if "_" in input_string:
        words = input_string.split("_")  # Split the string by underscores
        result = "".join([word.capitalize() for word in words])  # Capitalize each word
        return result
    else:
        return input_string


class ImportGraphToRules(Step):
    """The step extracts data model from RDF graph and generates NEAT transformation rules object."""

    description = "The step extracts data model from RDF graph and generates NEAT transformation rules object. \
    The rules object can be serialized to excel file or used directly in other steps."
    category = CATEGORY
    version = "private-alpha"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="excel_file_path", value="staging/rules.xlsx", label="Relative path for the Excel rules storage."
        ),
        Configurable(
            name="max_number_of_instances",
            value="-1",
            label="Maximum number of instances per class to process, -1 means all instances",
        ),
    ]

    def run(self, graph_store: SourceGraph | SolutionGraph) -> FlowMessage:  # type: ignore[override, syntax]
        excel_file_path = self.data_store_path / Path(self.configs["excel_file_path"])
        report_file_path = excel_file_path.parent / f"report_{excel_file_path.stem}.txt"

        try:
            rules = importer.GraphImporter(
                graph_store.graph.graph, int(self.configs["max_number_of_instances"])
            ).to_rules()
        except Exception:
            rules = importer.GraphImporter(
                graph_store.graph.graph, int(self.configs["max_number_of_instances"])
            ).to_rules(skip_validation=True)

        assert isinstance(rules, Rules)
        exporter.ExcelExporter.from_rules(rules).export_to_file(excel_file_path)

        if report := importer.ExcelImporter(filepath=excel_file_path).to_raw_rules().validate_rules():
            report_file_path.write_text(report)

        relative_excel_file_path = str(excel_file_path).split("/data/")[1]
        relative_report_file_path = str(report_file_path).split("/data/")[1]

        output_text = (
            "<p></p>"
            "Rules imported from Graph can be downloaded here : "
            f'<a href="/data/{relative_excel_file_path}?{time.time()}" '
            f'target="_blank">{excel_file_path.stem}.xlsx</a>'
            "<p></p>"
            "Report can be downloaded here : "
            f'<a href="/data/{relative_report_file_path}?{time.time()}" '
            f'target="_blank">{report_file_path.stem}.txt</a>'
        )

        return FlowMessage(output_text=output_text)


class ImportExcelValidator(Step):
    """This step import rules from the Excel file and validates it."""

    description = "This step imports rules from an excel file "
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Report Formatter",
            value=next(iter(FORMATTER_BY_NAME.keys())),
            label="The format of the report for the validation of the rules",
            options=list(FORMATTER_BY_NAME),
        ),
        Configurable(
            name="role",
            value="infer",
            label="For what role Rules are intended?",
            options=["infer", *RoleTypes.__members__.keys()],
        ),
    ]

    def run(self, flow_message: FlowMessage) -> (FlowMessage, MultiRuleData):  # type: ignore[syntax, override]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)
        try:
            rules_file_path = flow_message.payload["full_path"]
        except (KeyError, TypeError):
            error_text = "Expected input payload to contain 'full_path' key."
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)
        # if role is None, it will be inferred from the rules file
        role = self.configs.get("role")
        role_enum = None
        if role != "infer" and role is not None:
            role_enum = RoleTypes[role]

        excel_importer = importers.ExcelImporter(rules_file_path)
        rules, issues = excel_importer.to_rules(role=role_enum, errors="continue")

        if rules is None:
            output_dir = self.data_store_path / Path("staging")
            report_writer = FORMATTER_BY_NAME[self.configs["Report Formatter"]]()
            report_writer.write_to_file(issues, file_or_dir_path=output_dir)
            report_file = report_writer.default_file_name
            error_text = (
                "<p></p>"
                f'<a href="/data/staging/{report_file}?{time.time()}" '
                f'target="_blank">Failed to validate rules, click here for report</a>'
            )
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        output_text = "Rules validation passed successfully!"

        return FlowMessage(output_text=output_text), MultiRuleData.from_rules(rules)


class ImportFromDataModelStorage(Step):
    """This step import rules from the Excel file and validates it."""

    description = "This step imports rules from CDF Data Model"
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Data Model ID",
            value="",
            label="The ID of the Data Model to import. Written at 'my_space:my_data_model(version=1)'",
            type="string",
            required=True,
        ),
        Configurable(
            name="Report Formatter",
            value=next(iter(FORMATTER_BY_NAME.keys())),
            label="The format of the report for the validation of the rules",
            options=list(FORMATTER_BY_NAME),
        ),
        Configurable(
            name="role",
            value="infer",
            label="For what role Rules are intended?",
            options=["infer", *RoleTypes.__members__.keys()],
        ),
    ]

    def run(self, cdf_client: CogniteClient) -> (FlowMessage, MultiRuleData):  # type: ignore[syntax, override]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        datamodel_id_str = self.configs.get("Data Model ID")
        if datamodel_id_str is None:
            error_text = "Expected input payload to contain 'Data Model ID' key."
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        datamodel_entity = DataModelEntity.from_raw(datamodel_id_str)
        if datamodel_entity.space is Undefined:
            error_text = (
                f"Data Model ID should be in the format 'my_space:my_data_model(version=1)' "
                f"or 'my_space:my_data_model', failed to parse space from {datamodel_id_str}"
            )
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        dms_importer = importers.DMSImporter.from_data_model_id(cdf_client, datamodel_entity.as_id())

        # if role is None, it will be inferred from the rules file
        role = self.configs.get("role")
        role_enum = None
        if role != "infer" and role is not None:
            role_enum = RoleTypes[role]

        rules, issues = dms_importer.to_rules(role=role_enum, errors="continue")

        if rules is None:
            output_dir = self.data_store_path / Path("staging")
            report_writer = FORMATTER_BY_NAME[self.configs["Report Formatter"]]()
            report_writer.write_to_file(issues, file_or_dir_path=output_dir)
            report_file = report_writer.default_file_name
            error_text = (
                "<p></p>"
                f'<a href="/data/staging/{report_file}?{time.time()}" '
                f'target="_blank">Failed to validate rules, click here for report</a>'
            )
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        output_text = "Rules import and validation passed successfully!"

        return FlowMessage(output_text=output_text), MultiRuleData.from_rules(rules)
