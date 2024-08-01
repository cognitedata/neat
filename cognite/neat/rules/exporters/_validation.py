import warnings
from collections import defaultdict
from collections.abc import Iterable
from typing import Literal, overload

from cognite.neat.exceptions import wrangle_warnings
from cognite.neat.issues.neat_warnings.identifier import RegexViolationWarning
from cognite.neat.rules.models import InformationRules
from cognite.neat.rules.models.entities import ClassEntity
from cognite.neat.rules.models.information import InformationProperty
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
                    RegexViolationWarning(
                        class_.class_.suffix,
                        VIEW_ID_COMPLIANCE_REGEX,
                        "Class",
                        "View ID",
                        "The class id should be DMS compliant to write to CDF.",
                    ),
                    stacklevel=2,
                )
                flag = False

        for _, property_ in enumerate(rules.properties):
            # check class id which would resolve as view/container id
            if not PATTERNS.view_id_compliance.match(property_.class_.suffix):
                warnings.warn(
                    RegexViolationWarning(
                        property_.class_.suffix,
                        VIEW_ID_COMPLIANCE_REGEX,
                        "Class",
                        "View ID",
                        "The class id should be DMS compliant to write to CDF.",
                    ),
                    stacklevel=2,
                )
                flag = False

            # check property id which would resolve as view/container id
            if not PATTERNS.dms_property_id_compliance.match(property_.property_):
                warnings.warn(
                    RegexViolationWarning(
                        property_.property_,
                        DMS_PROPERTY_ID_COMPLIANCE_REGEX,
                        "Property",
                        "DMS Property ID",
                        "The property id should be DMS compliant to write to CDF.",
                    ),
                    stacklevel=2,
                )
                flag = False

    if return_report:
        return flag, wrangle_warnings(validation_warnings)
    else:
        return flag


def duplicated_properties(
    properties: Iterable[InformationProperty],
) -> dict[tuple[ClassEntity, str], list[tuple[int, InformationProperty]]]:
    class_properties_by_id: dict[tuple[ClassEntity, str], list[tuple[int, InformationProperty]]] = defaultdict(list)
    for prop_no, prop in enumerate(properties):
        class_properties_by_id[(prop.class_, prop.property_)].append((prop_no, prop))
    return {k: v for k, v in class_properties_by_id.items() if len(v) > 1}


def property_ids_camel_case_compliant(rules) -> bool | tuple[bool, list[dict]]:
    raise NotImplementedError()


def class_id_pascal_case_compliant(rules) -> bool | tuple[bool, list[dict]]:
    raise NotImplementedError()
