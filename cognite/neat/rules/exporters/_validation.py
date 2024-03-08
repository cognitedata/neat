import re
import warnings
from typing import Literal, overload

from cognite.neat.exceptions import wrangle_warnings
from cognite.neat.rules import exceptions
from cognite.neat.rules.models._rules import InformationRules
from cognite.neat.rules.models._rules._types._base import DMS_PROPERTY_ID_COMPLIANCE_REGEX, VIEW_ID_COMPLIANCE_REGEX


@overload
def are_entity_names_dms_compliant(rules: InformationRules, return_report: Literal[True]) -> tuple[bool, list[dict]]:
    ...


@overload
def are_entity_names_dms_compliant(rules: InformationRules, return_report: Literal[False] = False) -> bool:
    ...


def are_entity_names_dms_compliant(
    rules: InformationRules, return_report: bool = False
) -> bool | tuple[bool, list[dict]]:
    """Check if data model definitions are valid."""

    flag: bool = True
    with warnings.catch_warnings(record=True) as validation_warnings:
        for class_ in rules.classes:
            if not re.match(VIEW_ID_COMPLIANCE_REGEX, class_.class_.suffix):
                warnings.warn(
                    exceptions.EntityIDNotDMSCompliant(
                        "Class", class_.class_.versioned_id, f"[Classes/Class/{class_.class_.versioned_id}]"
                    ).message,
                    category=exceptions.EntityIDNotDMSCompliant,
                    stacklevel=2,
                )
                flag = False

        for row, property_ in enumerate(rules.properties):
            # check class id which would resolve as view/container id
            if not re.match(VIEW_ID_COMPLIANCE_REGEX, property_.class_.suffix):
                warnings.warn(
                    exceptions.EntityIDNotDMSCompliant(
                        "Class", property_.class_.versioned_id, f"[Properties/Class/{row}]"
                    ).message,
                    category=exceptions.EntityIDNotDMSCompliant,
                    stacklevel=2,
                )
                flag = False

            # check property id which would resolve as view/container id
            if not re.match(DMS_PROPERTY_ID_COMPLIANCE_REGEX, property_.property_):
                warnings.warn(
                    exceptions.EntityIDNotDMSCompliant(
                        "Property", property_.property_, f"[Properties/Property/{row}]"
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
def are_properties_redefined(rules: InformationRules, return_report: Literal[True]) -> tuple[bool, list[dict]]:
    ...


@overload
def are_properties_redefined(rules: InformationRules, return_report: Literal[False] = False) -> bool:
    ...


def are_properties_redefined(rules: InformationRules, return_report: bool = False) -> bool | tuple[bool, list[dict]]:
    flag: bool = False
    with warnings.catch_warnings(record=True) as validation_warnings:
        analyzed_properties: dict[str, list[str]] = {}
        for property_ in rules.properties:
            if property_.property_ not in analyzed_properties:
                analyzed_properties[property_.property_] = [property_.class_.versioned_id]
            elif property_.class_ in analyzed_properties[property_.property_]:
                flag = True
                warnings.warn(
                    exceptions.PropertyRedefined(property_.property_, property_.class_.versioned_id).message,
                    category=exceptions.EntityIDNotDMSCompliant,
                    stacklevel=2,
                )

            else:
                analyzed_properties[property_.property_].append(property_.class_.versioned_id)

    if return_report:
        return flag, wrangle_warnings(validation_warnings)
    else:
        return flag


def property_ids_camel_case_compliant(rules) -> bool | tuple[bool, list[dict]]:
    raise NotImplementedError()


def class_id_pascal_case_compliant(rules) -> bool | tuple[bool, list[dict]]:
    raise NotImplementedError()
