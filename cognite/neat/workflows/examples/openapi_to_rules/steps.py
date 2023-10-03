# import datetime
# import json
# from pathlib import Path

# from rdflib import Namespace
# from cognite.neat.rules.models import Class, Metadata, Property, TransformationRules
# from cognite.neat.workflows.model import FlowMessage
# from cognite.neat.workflows.steps.data_contracts import RulesData

# from cognite.neat.workflows.steps.step_model import Configurable, Step
# import logging
# import yaml


# class OpenApiToRules(Step):
#     """The step extracts schema from OpenAPI spec and generates NEAT transformation rules object."""
#     description = "The step extracts schema from OpenAPI spec and generates NEAT transformation rules object."
#     category = "openapi"
#     version = "0.1.0-alpha"
#     configurables = [
#         Configurable(
#             name="openapi_spec_file_path",
#             value="workflows/openapi_to_rules/source_data/openapi.json",
#             label="Relative path to the OpenAPI spec file.The file can be in either json or yaml format.",
#         )
#     ]

#     def run(self) -> (FlowMessage, RulesData):
#         openapi_file_path = Path(self.data_store_path) / Path(self.configs["openapi_spec_file_path"])
#         rules = self.open_api_to_rules(openapi_file_path)
#         return (FlowMessage(output_text="Generated Rules from OpenApi spec"), RulesData(rules=rules))

#     def open_api_to_rules(self, open_api_spec_file_path: Path) -> TransformationRules:
#         """Converts OpenAPI spec to NEAT transformation rules object. """
#         with open_api_spec_file_path.open("r") as openapi_file:
#             if open_api_spec_file_path.suffix == ".json":
#                 openapi_spec = json.load(openapi_file)
#             elif open_api_spec_file_path.suffix == ".yaml":
#                 openapi_spec = yaml.safe_load(openapi_file)

#         metadata = Metadata(
#             title="OpenAPI to DM transformation rules",
#             description="OpenAPI to DM transformation rules",
#             version="0.1",
#             creator="Cognite",
#             created=datetime.datetime.now(),
#             namespace=Namespace("http://purl.org/cognite/neat#"),
#             prefix="neat",
#             dataModelName="OpenAPI",
#             cdf_space_name="OpenAPI",
#             data_model_name="OpenAPI",
#         )

#         classes: dict[str, Class] = {}
#         properties: dict[str, Property] = {}

#         # Loop through OpenAPI components
#         for component_name, component_info in openapi_spec.get("components", {}).get("schemas", {}).items():
#             class_name = self.remove_underscores_and_capitalize(component_name)
#             class_name = self.get_dms_compatible_name(class_name)
#             class_id = class_name
#             logging.info(f" OpenAPi parser : Processing class {class_id} ")
#             try:
#                 class_ = Class(
#                     class_id=class_id,
#                     class_name=class_name,
#                     description=component_info.get("description", component_info.get("title", "empty")),
#                     is_abstract=False,
#                     is_interface=False,
#                 )
#                 classes[class_id] = class_
#                 # Loop through properties of OpenApi spec]
#                 self.process_properies(properties, class_id, class_name, component_info)
#             except Exception as e:
#                 logging.error(f" OpenAPi parser : Error creating class {class_id}: {e}")

#         rules = TransformationRules(
#             metadata=metadata, classes=classes, properties=properties, prefixes={}, instances=[]
#         )

#         return rules

#     def process_properies(
#         self,
#         rules_properties: dict[str, Property],
#         class_id: str,
#         class_name: str,
#         component: dict,
#         parent_property_name: str = None,
#     ):
#         # component can have keys : type, description, properties, required, title, allOf, anyOf, oneOf§
#         logging.info(f" OpenAPi parser : Processing properties for class {class_id} , component {component}")
#         for component_name, component_info in component.items():
#             if component_name == "allOf" or component_name == "anyOf" or component_name == "oneOf":
#                 for sub_component in component_info:
#                     self.process_properies(rules_properties, class_id, class_name, sub_component, component_name)
#             elif component_name == "properties":
#                 for prop_name, prop_info in component_info.items():
#                     prop_id = prop_name
#                     if prop_name == "allOf" or prop_name == "anyOf" or prop_name == "oneOf":
#                         if isinstance(prop_info, list):
#                             prop_type = prop_info[0].get("type", "string")
#                         else:
#                             logging.error(f" !!!!! prop info is not a list . its: {prop_info} ")

#                     else:
#                         prop_type = prop_info.get("type", "string")
#                         if prop_type == "array":
#                             self.process_properies(
#                                 rules_properties, class_id, class_name, prop_info.get("items", {}), prop_name
#                             )
#                             continue
#                     expected_value_type = self.map_open_api_type(prop_type)
#                     if prop_name == "$ref":
#                         ref_class = self.get_ref_class_name(prop_info.get("$ref", ""))
#                         expected_value_type = ref_class
#                     try:
#                         logging.info(f" OpenAPi parser : Processing property {prop_id} ")
#                         prop = Property(
#                             class_id=class_id,
#                             class_name=class_name,
#                             property_id=self.get_dms_compatible_name(prop_id),
#                             property_name=self.get_dms_compatible_name(prop_name.replace(".", "_")),
#                             property_type="ObjectProperty",
#                             description=prop_info.get("description", prop_info.get("title", "empty")),
#                             expected_value_type=expected_value_type,
#                             cdf_resource_type="Asset",
#                             resource_type_property="Asset",
#                             rule_type="rdfpath",
#                             rule=f"neat:{class_name}(neat:{prop_name})",
#                             label="linked to",
#                         )
#                         rules_properties[class_id + prop_id] = prop
#                     except Exception as e:
#                         logging.error(f" OpenAPi parser : Error creating property {prop_id}: {e}")
#             elif component_name == "$ref":
#                 ref_class = self.get_ref_class_name(component_info)
#                 logging.debug(f" OpenAPi parser : REF class {ref_class} ")
#                 prop = Property(
#                     class_id=class_id,
#                     class_name=class_name,
#                     property_id=parent_property_name,
#                     property_name=parent_property_name,
#                     property_type="ObjectProperty",
#                     description="no",
#                     expected_value_type=ref_class,
#                     cdf_resource_type="Asset",
#                     resource_type_property="Asset",
#                     rule_type="rdfpath",
#                     rule=f"neat:{class_name}(neat:{parent_property_name})",
#                     label="linked to",
#                 )
#                 rules_properties[class_id + parent_property_name] = prop

#     def get_ref_class_name(self, ref: str) -> str:
#         return self.get_dms_compatible_name(ref.split("/")[-1])

#     def get_dms_compatible_name(self, name: str) -> str:
#         # reserverd words in DMS
#         reserved_words_mapping = {
#             "space": "src_space",
#             "externalId": "external_id",
#             "createdTime": "created_time",
#             "lastUpdatedTime": "last_updated_time",
#             "deletedTime": "deleted_time",
#             "edge_id": "src_edge_id",
#             "node_id": "src_node_id",
#             "project_id": "src_project_id",
#             "property_group": "src_property_group",
#             "seq": "src_seq",
#             "tg_table_name": "src__table_name",
#             "extensions": "src_extensions",
#         }
#         if name in reserved_words_mapping:
#             return reserved_words_mapping[name]
#         else:
#             return name.replace(".", "_")

#     def remove_underscores_and_capitalize(self, input_string: str):
#         """Remove underscores and capitalize each word in the string , the convertion is done to improve complienc with DMS naming conventions"""
#         if "_" in input_string:
#             words = input_string.split("_")  # Split the string by underscores
#             result = "".join([word.capitalize() for word in words])  # Capitalize each word
#             return result
#         else:
#             return input_string

#     def map_open_api_type(self, openapi_type: str) -> str:
#         """Map OpenAPI type to NEAT compatible types"""
#         if openapi_type == "object":
#             datatype = "json"
#         elif openapi_type == "array":
#             datatype = "sequence"
#         elif openapi_type == "number":
#             datatype = "float"
#         else:
#             return openapi_type  # Default to string
#         return datatype
