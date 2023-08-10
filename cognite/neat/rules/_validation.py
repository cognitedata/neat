import re
from typing import overload
import warnings

from cognite.neat.rules import _exceptions
from cognite.neat.rules.models import TransformationRules, data_model_name_compliance_regex


@overload
def are_entity_names_dms_compliant(
    transformation_rules: TransformationRules, return_report: bool = False
) -> tuple[bool, list[dict]]:
    ...


@overload
def are_entity_names_dms_compliant(transformation_rules: TransformationRules, return_report: bool = False) -> bool:
    ...


def are_entity_names_dms_compliant(
    transformation_rules: TransformationRules, return_report: bool = False
) -> bool | tuple[bool, list[dict]]:
    """Check if data model definitions are valid."""

    flag: bool = True
    with warnings.catch_warnings(record=True) as validation_warnings:
        for class_ in transformation_rules.classes.values():
            if not re.match(data_model_name_compliance_regex, class_.class_id):
                warnings.warn(
                    _exceptions.Warning600("Class", class_.class_id, f"[Classes/Class/{class_.class_id}]").message,
                    category=_exceptions.Warning600,
                    stacklevel=2,
                )
                flag = False

        for row, property_ in transformation_rules.properties.items():
            if not re.match(data_model_name_compliance_regex, property_.class_id):
                warnings.warn(
                    _exceptions.Warning600("Class", property_.class_id, f"[Properties/Class/{row}]").message,
                    category=_exceptions.Warning600,
                    stacklevel=2,
                )
                flag = False
            if not re.match(data_model_name_compliance_regex, property_.property_id):
                warnings.warn(
                    _exceptions.Warning600("Property", property_.property_id, f"[Properties/Property/{row}]").message,
                    category=_exceptions.Warning600,
                    stacklevel=2,
                )
                flag = False
            if not re.match(data_model_name_compliance_regex, property_.expected_value_type):
                warnings.warn(
                    _exceptions.Warning600(
                        "Value type", property_.expected_value_type, f"[Properties/Type/{row}]"
                    ).message,
                    category=_exceptions.Warning600,
                    stacklevel=2,
                )
                flag = False

    if return_report:
        return flag, _exceptions.wrangle_warnings(validation_warnings)
    else:
        return flag


@overload
def are_properties_redefined(
    transformation_rules: TransformationRules, return_report: bool = False
) -> tuple[bool, list[dict]]:
    ...


@overload
def are_properties_redefined(transformation_rules: TransformationRules, return_report: bool = False) -> bool:
    ...


def are_properties_redefined(
    transformation_rules: TransformationRules, return_report: bool = False
) -> bool | tuple[bool, list[dict]]:
    flag: bool = False
    with warnings.catch_warnings(record=True) as validation_warnings:
        analyzed_properties = {}
        for property_ in transformation_rules.properties.values():
            if property_.property_id not in analyzed_properties:
                analyzed_properties[property_.property_id] = [property_.class_id]
            elif property_.class_id in analyzed_properties[property_.property_id]:
                flag = True
                warnings.warn(
                    _exceptions.Warning601(property_.class_id, property_.property_id).message,
                    category=_exceptions.Warning600,
                    stacklevel=2,
                )

            else:
                analyzed_properties[property_.property_id].append(property_.class_id)

    if return_report:
        return flag, _exceptions.wrangle_warnings(validation_warnings)
    else:
        return flag


def property_ids_camel_case_compliant(transformation_rules) -> bool | tuple[bool, list[dict]]:
    ...


def class_id_pascal_case_compliant(transformation_rules) -> bool | tuple[bool, list[dict]]:
    ...
