import warnings
from typing import Literal, overload

from cognite.neat.exceptions import wrangle_warnings
from cognite.neat.rules.issues.dms import EntityIDNotDMSCompliantWarning
from cognite.neat.rules.issues.importing import PropertyRedefinedWarning
from cognite.neat.rules.models import InformationRules
from cognite.neat.utils.regex_patterns import DMS_PROPERTY_ID_COMPLIANCE_REGEX, PATTERNS, VIEW_ID_COMPLIANCE_REGEX


@overload
def are_entity_names_dms_compliant(
    rules: InformationRules, return_report: Literal[True]
) -> tuple[bool, list[dict]]: ...


@overload
def are_entity_names_dms_compliant(rules: InformationRules, return_report: Literal[False] = False) -> bool: ...


def are_entity_names_dms_compliant(
    rules: InformationRules, return_report: bool = False
) -> bool | tuple[bool, list[dict]]:
    """Check if data model definitions are valid."""

    flag: bool = True
    with warnings.catch_warnings(record=True) as validation_warnings:
        for class_ in rules.classes:
            if not PATTERNS.view_id_compliance.match(class_.class_.suffix):
                warnings.warn(
                    EntityIDNotDMSCompliantWarning(class_.class_.versioned_id, "Class", VIEW_ID_COMPLIANCE_REGEX),
                    stacklevel=2,
                )
                flag = False

        for _, property_ in enumerate(rules.properties):
            # check class id which would resolve as view/container id
            if not PATTERNS.view_id_compliance.match(property_.class_.suffix):
                warnings.warn(
                    EntityIDNotDMSCompliantWarning(
                        property_.class_.versioned_id,
                        "Class",
                        VIEW_ID_COMPLIANCE_REGEX,
                    ),
                    stacklevel=2,
                )
                flag = False

            # check property id which would resolve as view/container id
            if not PATTERNS.dms_property_id_compliance.match(property_.property_):
                warnings.warn(
                    EntityIDNotDMSCompliantWarning(property_.property_, "Property", DMS_PROPERTY_ID_COMPLIANCE_REGEX),
                    stacklevel=2,
                )
                flag = False

    if return_report:
        return flag, wrangle_warnings(validation_warnings)
    else:
        return flag


@overload
def are_properties_redefined(rules: InformationRules, return_report: Literal[True]) -> tuple[bool, list[dict]]: ...


@overload
def are_properties_redefined(rules: InformationRules, return_report: Literal[False] = False) -> bool: ...


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
                    PropertyRedefinedWarning(property_.property_, property_.class_.versioned_id),
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
