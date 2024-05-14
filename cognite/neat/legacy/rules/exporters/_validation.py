import re
import warnings
from typing import Literal, overload

from cognite.neat.exceptions import wrangle_warnings
from cognite.neat.legacy.rules import exceptions
from cognite.neat.legacy.rules.models.rules import (
    Rules,
    dms_property_id_compliance_regex,
    value_id_compliance_regex,
    view_id_compliance_regex,
)


@overload
def are_entity_names_dms_compliant(
    transformation_rules: Rules, return_report: Literal[True]
) -> tuple[bool, list[dict]]: ...


@overload
def are_entity_names_dms_compliant(transformation_rules: Rules, return_report: Literal[False] = False) -> bool: ...


def are_entity_names_dms_compliant(
    transformation_rules: Rules, return_report: bool = False
) -> bool | tuple[bool, list[dict]]:
    """Check if data model definitions are valid."""

    flag: bool = True
    with warnings.catch_warnings(record=True) as validation_warnings:
        for class_ in transformation_rules.classes.values():
            if not re.match(view_id_compliance_regex, class_.class_id):
                warnings.warn(
                    exceptions.EntityIDNotDMSCompliant(
                        "Class", class_.class_id, f"[Classes/Class/{class_.class_id}]"
                    ).message,
                    category=exceptions.EntityIDNotDMSCompliant,
                    stacklevel=2,
                )
                flag = False

        for row, property_ in transformation_rules.properties.items():
            # check class id which would resolve as view/container id
            if not re.match(view_id_compliance_regex, property_.class_id):
                warnings.warn(
                    exceptions.EntityIDNotDMSCompliant(
                        "Class", property_.class_id, f"[Properties/Class/{row}]"
                    ).message,
                    category=exceptions.EntityIDNotDMSCompliant,
                    stacklevel=2,
                )
                flag = False

            # check property id which would resolve as view/container id
            if not re.match(dms_property_id_compliance_regex, property_.property_id):
                warnings.warn(
                    exceptions.EntityIDNotDMSCompliant(
                        "Property", property_.property_id, f"[Properties/Property/{row}]"
                    ).message,
                    category=exceptions.EntityIDNotDMSCompliant,
                    stacklevel=2,
                )
                flag = False

            # check container external id
            if property_.container and not re.match(view_id_compliance_regex, property_.container.external_id):
                warnings.warn(
                    exceptions.EntityIDNotDMSCompliant(
                        "Container", property_.container.external_id, f"[Properties/Container/{row}]"
                    ).message,
                    category=exceptions.EntityIDNotDMSCompliant,
                    stacklevel=2,
                )
                flag = False

            # check container property external id
            if property_.container_property and not re.match(
                dms_property_id_compliance_regex, property_.container_property
            ):
                warnings.warn(
                    exceptions.EntityIDNotDMSCompliant(
                        "Container Property", property_.container_property, f"[Properties/Container Property/{row}]"
                    ).message,
                    category=exceptions.EntityIDNotDMSCompliant,
                    stacklevel=2,
                )
                flag = False

            # expected value type, as it is case sensitive should be ok
            if not re.match(value_id_compliance_regex, property_.expected_value_type.external_id):
                warnings.warn(
                    exceptions.EntityIDNotDMSCompliant(
                        "Value type", property_.expected_value_type.external_id, f"[Properties/Type/{row}]"
                    ).message,
                    category=exceptions.EntityIDNotDMSCompliant,
                    stacklevel=2,
                )
                flag = False

    if return_report:
        return flag, wrangle_warnings(validation_warnings)
    else:
        return flag


@overload
def are_properties_redefined(transformation_rules: Rules, return_report: Literal[True]) -> tuple[bool, list[dict]]: ...


@overload
def are_properties_redefined(transformation_rules: Rules, return_report: Literal[False] = False) -> bool: ...


def are_properties_redefined(
    transformation_rules: Rules, return_report: bool = False
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
                    exceptions.PropertyRedefined(property_.property_id, property_.class_id).message,
                    category=exceptions.EntityIDNotDMSCompliant,
                    stacklevel=2,
                )

            else:
                analyzed_properties[property_.property_id].append(property_.class_id)

    if return_report:
        return flag, wrangle_warnings(validation_warnings)
    else:
        return flag


def property_ids_camel_case_compliant(transformation_rules) -> bool | tuple[bool, list[dict]]:
    raise NotImplementedError()


def class_id_pascal_case_compliant(transformation_rules) -> bool | tuple[bool, list[dict]]:
    raise NotImplementedError()
