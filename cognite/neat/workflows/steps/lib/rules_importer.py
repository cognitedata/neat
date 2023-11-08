import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import ClassVar

import yaml
from rdflib import Namespace

from cognite.neat.rules import exporter, importer
from cognite.neat.rules.models.rdfpath import TransformationRuleType
from cognite.neat.rules.models.rules import Class, Classes, Metadata, Properties, Property, Rules
from cognite.neat.workflows.model import FlowMessage
from cognite.neat.workflows.steps.data_contracts import RulesData, SolutionGraph, SourceGraph
from cognite.neat.workflows.steps.step_model import Configurable, Step

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()

__all__ = ["OpenApiToRules", "ArbitraryJsonYamlToRules", "GraphToRules", "OntologyToRules"]


class OntologyToRules(Step):
    """The step extracts schema from OpenApi/Swagger specification and generates NEAT transformation rules object."""

    description = "The step extracts NEAT rules object from OWL Ontology and \
        exports them as an Excel rules files for further editing."
    category = CATEGORY
    version = "0.1.0-alpha"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="ontology_file_path", value="staging/ontology.ttl", label="Relative path to the OWL ontology file."
        ),
        Configurable(
            name="excel_file_path", value="staging/rules.xlsx", label="Relative path for the Excel rules storage."
        ),
    ]

    def run(self) -> FlowMessage:  # type: ignore[override, syntax]
        ontology_file_path = self.data_store_path / Path(self.configs["ontology_file_path"])
        excel_file_path = self.data_store_path / Path(self.configs["excel_file_path"])
        report_file_path = excel_file_path.parent / f"report_{excel_file_path.stem}.txt"

        rules = importer.OWLImporter(ontology_file_path).to_rules(skip_validation=True)
        assert isinstance(rules, Rules)
        exporter.ExcelExporter.from_rules(rules).export_to_file(excel_file_path)

        if report := importer.ExcelImporter(filepath=excel_file_path).to_raw_rules().validate_rules():
            report_file_path.write_text(report)

        relative_excel_file_path = str(excel_file_path).split("/data/")[1]
        relative_report_file_path = str(report_file_path).split("/data/")[1]

        output_text = (
            "<p></p>"
            "Rules generated from OWL Ontology can be downloaded here : "
            f'<a href="http://localhost:8000/data/{relative_excel_file_path}?{time.time()}" '
            f'target="_blank">{excel_file_path.stem}.xlsx</a>'
            "<p></p>"
            "Report can be downloaded here : "
            f'<a href="http://localhost:8000/data/{relative_report_file_path}?{time.time()}" '
            f'target="_blank">{report_file_path.stem}.txt</a>'
        )

        return FlowMessage(output_text=output_text)


class OpenApiToRules(Step):
    """The step extracts schema from OpenApi/Swagger specification and generates NEAT transformation rules object."""

    description = "The step extracts schema from OpenAPI specification and generates NEAT transformation rules object. \
    The rules object can be serialized to excel file or used directly in other steps."
    category = CATEGORY
    version = "0.1.0-alpha"
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
        self.processed_properies_counter = 0
        self.failed_classes_counter = 0
        self.failed_properties_counter = 0
        self.failed_classes: dict[str, str] = {}
        self.failed_properties: dict[str, str] = {}
        self.is_fdm_compatibility_mode = self.configs["fdm_compatibility_mode"] == "True"
        rules = self.open_api_to_rules(openapi_file_path)
        report = f" Generated Rules and source data model from OpenApi specs   \
        <p> Processed {self.processed_classes_counter} classes and {self.processed_properies_counter} properties. </p> \
        <p> Failed to process {self.failed_classes_counter} classes and \
        {self.failed_properties_counter} properties. </p>"
        report_obj = {
            "processed_classes_counter": self.processed_classes_counter,
            "processed_properies_counter": self.processed_properies_counter,
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
            data_model_name="OpenAPI",
            cdf_space_name="OpenAPI",
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
                            property_name=get_dms_compatible_name(prop_name)
                            if self.is_fdm_compatibility_mode
                            else prop_name,
                            property_type="ObjectProperty",
                            description=prop_info.get("description", prop_info.get("title", "empty")),
                            expected_value_type=expected_value_type,
                            cdf_resource_type=["Asset"],
                            resource_type_property="Asset",  # type: ignore
                            rule_type=TransformationRuleType("rdfpath"),
                            rule=f"neat:{class_name}(neat:{prop_name})",
                            label="linked to",
                        )
                        self.processed_properies_counter += 1
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
                        expected_value_type=ref_class,
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


class ArbitraryJsonYamlToRules(Step):
    """The step extracts schema from arbitrary json or yaml file and generates NEAT transformation rules object."""

    description = "The step extracts schema from arbitrary json file and generates NEAT transformation rules object."
    category = CATEGORY
    version = "0.1.0-alpha"
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
            cdf_space_name="OpenAPI",
            data_model_name="OpenAPI",
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
                expected_value_type=property_type,
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


class GraphToRules(Step):
    """The step extracts data model from RDF graph and generates NEAT transformation rules object."""

    description = "The step extracts data model from RDF graph and generates NEAT transformation rules object. \
    The rules object can be serialized to excel file or used directly in other steps."
    category = CATEGORY
    version = "0.1.0-alpha"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="file_name", value="inferred_transformations.xlsx", label="File name to store transformation rules."
        ),
        Configurable(name="storage_dir", value="staging", label="Directory to store Transformation Rules spreadsheet"),
        Configurable(
            name="max_number_of_instances",
            value="-1",
            label="Maximum number of instances per class to process, -1 means all instances",
        ),
    ]

    def run(self, graph_store: SourceGraph | SolutionGraph) -> FlowMessage:  # type: ignore[override, syntax]
        file_name = self.configs["file_name"]
        staging_dir_str = self.configs["storage_dir"]
        staging_dir = self.data_store_path / Path(staging_dir_str)
        staging_dir.mkdir(parents=True, exist_ok=True)

        spreadsheet_path = staging_dir / file_name

        raw_rules = importer.GraphImporter(
            graph_store.graph.graph, int(self.configs["max_number_of_instances"])
        ).to_raw_rules()
        exporter.ExcelExporter.from_rules(raw_rules).export_to_file(spreadsheet_path)

        output_text = (
            "<p></p>"
            "Rules imported using GraphImporter and can be downloaded as the Excel file:"
            f'<a href="http://localhost:8000/data/{staging_dir_str}/{file_name}?{time.time()}" '
            f'target="_blank">{file_name}</a>'
            "<p></p>"
            "Rules validation report can be downloaded as TXT file: "
            f'<a href="http://localhost:8000/data/{staging_dir_str}/{spreadsheet_path.stem}'
            f'_validation_report.txt?{time.time()}" '
            f'target="_blank">{spreadsheet_path.stem}_validation_report.txt</a>'
        )

        return FlowMessage(output_text=output_text)
