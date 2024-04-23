"""This module contains the definition of errors and warnings raised when dealing
with TransformationRules object. This includes underlying pydantic model, actual transformation rules
handling (such `rdfpath`), and rules loaders, parsers and exporters.

\nThe errors and warning are grouped by means of error codes:\n
- 0 - 99: errors and warnings raised when dealing with TransformationRules pydantic model
- 100 - 199: errors and warnings raised when parsing actual transformation rules, i.e. `rdfpath`
- 200 - 299: errors and warnings raised when dealing TransformationRules importers
- 300 - 399: errors and warnings raised when dealing TransformationRules parsers
- 400 - 499: errors and warnings raised when dealing TransformationRules exporters

"""

from typing import Any

from cognite.client.data_classes.data_modeling import ContainerId, DataModelId, ViewId
from rdflib import Namespace, URIRef

from cognite.neat.constants import DEFAULT_DOCS_URL
from cognite.neat.exceptions import NeatException, NeatWarning

DOCS_BASE_URL = f"{DEFAULT_DOCS_URL}api/exceptions.html#{__name__}"


class MultipleExceptions(NeatException):
    """This is used to gather multiple errors."""

    def __init__(self, errors: list[NeatException], verbose: bool = False):
        self.errors = errors
        self.message = f"Multiple errors occurred: {self.errors}"
        if verbose:
            self.message += f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        super().__init__(self.message)


################################################################################################
# RULES MODEL REPRESENTATION: 100 - 199 ########################################################
################################################################################################

# Exceptions:


class PrefixRegexViolation(NeatException):
    """Prefix, which is in the 'Metadata' sheet, does not respect defined regex expression

    Args:
        prefix: prefix that raised exception
        regex_expression: regex expression against which prefix is validated
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Check if prefix in the 'Metadata' sheet contains any illegal characters and
        respects the regex expression.

    """

    type_: str = "PrefixRegexViolation"
    code: int = 0
    description: str = "Prefix, which is in the 'Metadata' sheet, does not respect defined regex expression"
    example: str = (
        "If prefix is set to 'power grid', while regex expression does not "
        "allow spaces, the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check if prefix in the 'Metadata' sheet contains any illegal characters and respects the regex expression"
    )

    def __init__(self, prefix: str, regex_expression: str, verbose: bool = False):
        self.prefix = prefix
        self.regex_expression = regex_expression

        self.message = (
            f"Invalid prefix '{self.prefix}' stored in 'Metadata' sheet, it must obey regex {self.regex_expression}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PrefixMissing(NeatException):
    """Prefix, which is in the 'Metadata' sheet, is missing.

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    """

    type_: str = "PrefixMissing"
    code: int = 0
    description: str = "Prefix is missing from the 'Metadata' sheet."
    example: str = "There is no prefix in the 'Metadata' sheet."
    fix: str = "Specify the prefix if prefix in the 'Metadata' sheet."

    def __init__(self, verbose: bool = False):
        self.message = (
            f"Missing prefix stored in 'Metadata' sheet."
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class CDFSpaceRegexViolation(NeatException):
    """cdfSpaceName, which is in the 'Metadata' sheet, does not respect defined regex expression

    Args:
        cdf_space_name: cdf_space_name that raised exception
        regex_expression: regex expression against which cdf_space_name is validated
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Check if cdfSpaceName in the 'Metadata' sheet contains any illegal characters and
        respects the regex expression.

    """

    type_: str = "CDFSpaceRegexViolation"
    code: int = 1
    description: str = "cdfSpaceName, which is in the 'Metadata' sheet, does not respect defined regex expression"
    example: str = (
        "If cdfSpaceName is set to 'power grid', while regex expression does not "
        "allow spaces, the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check if cdfSpaceName in the 'Metadata' sheet "
        "contains any illegal characters and respects the regex expression"
    )

    def __init__(self, cdf_space_name: str, regex_expression: str, verbose: bool = False):
        self.cdf_space_name = cdf_space_name
        self.regex_expression = regex_expression

        self.message = (
            f"Invalid cdfSpaceName '{self.cdf_space_name}' stored in 'Metadata' sheet, "
            f"it must obey regex {self.regex_expression}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class MetadataSheetNamespaceNotValidURL(NeatException):
    """namespace, which is in the 'Metadata' sheet, does not respect defined regex expression

    Args:
        namespace: namespace that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Check if `namespace` in the `Metadata` sheet is properly constructed as valid URL
        containing only allowed characters.

    """

    type_: str = "MetadataSheetNamespaceNotValidURL"
    code: int = 2
    description: str = "namespace, which is in the 'Metadata' sheet, is not valid URL"
    example: str = "If we have 'authority:namespace' as namespace as it is not a valid URL this error will be raised"
    fix: str = (
        "Check if 'namespace' in the 'Metadata' sheet is properly "
        "constructed as valid URL containing only allowed characters"
    )

    def __init__(self, namespace: str, verbose: bool = False):
        self.namespace = namespace

        self.message = (
            f"Invalid namespace '{self.namespace}' stored in 'Metadata' sheet, it must be valid URL!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class MetadataSheetNamespaceNotDefined(NeatException):
    """namespace, which is in the 'Metadata' sheet, is not defined

    Args:
        namespace: namespace that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Check if `namespace` in the `Metadata` sheet is properly constructed as valid URL
        containing only allowed characters.

    """

    type_ = "MetadataSheetNamespaceNotDefined"
    code: int = 2
    description: str = "namespace, which is in the 'Metadata' sheet, is missing"
    example: str = "Example of a valid namespace 'http://www.w3.org/ns/sparql#'"
    fix: str = "Define the 'namespace' in the 'Metadata' sheet."

    def __init__(self, verbose: bool = False):
        self.message = (
            f"Missing namespace  in 'Metadata' sheet." f"\nFor more information visit: {DOCS_BASE_URL}.{self.type_}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class DataModelIdRegexViolation(NeatException):
    """dataModelName, which is in the 'Metadata' sheet, does not respect defined regex expression

    Args:
        data_model_name: data_model_name that raised exception
        regex_expression: regex expression against which data_model_name is validated
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Check if `dataModelName` in the `Metadata` sheet contains any illegal
        characters and respects the regex expression

    """

    type_: str = "DataModelIdRegexViolation"
    code: int = 3
    description: str = "external_id, which is in the 'Metadata' sheet, does not respect defined regex expression"
    example: str = (
        "If external_id is set to 'power grid data model', while regex expression does not "
        "allow spaces, the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check if external_id in the 'Metadata' sheet contains any illegal "
        "characters and respects the regex expression"
    )

    def __init__(self, data_model_id: str, regex_expression: str, verbose: bool = False):
        self.data_model_id = data_model_id
        self.regex_expression = regex_expression

        self.message = (
            f"Invalid data model external_id '{self.data_model_id}' stored in 'Metadata' sheet, "
            f"it must obey regex {self.regex_expression}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class VersionRegexViolation(NeatException):
    """version, which is in the 'Metadata' sheet, does not respect defined regex expression

    Args:
        version: version that raised exception
        regex_expression: regex expression against which version is validated
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Check if `version` in the `Metadata` sheet contains any illegal
        characters and respects the regex expression

    """

    type_: str = "VersionRegexViolation"
    code: int = 4
    description: str = "version, which is in the 'Metadata' sheet, does not respect defined regex expression"
    example: str = (
        "If version is set to '1.2.3 alpha4443', while regex expression does not "
        "allow spaces, the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check if version in the 'Metadata' sheet contains any illegal characters and respects the regex expression"
    )

    def __init__(self, version: str, regex_expression: str, verbose: bool = False):
        self.version = version
        self.regex_expression = regex_expression

        self.message = (
            f"Invalid version '{self.version}' stored in 'Metadata' sheet, it must obey regex {self.regex_expression}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ClassSheetClassIDRegexViolation(NeatException):
    """Class ID, which is stored in the column 'Class' in the 'Classes' sheet, does not
    respect defined regex expression

    Args:
        class_id: class_id that raised exception
        regex_expression: regex expression against which class_id is validated
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Check definition of class ids in 'Class' column in 'Classes' sheet and
        make sure to respect the regex expression by removing any illegal characters

    """

    type_: str = "ClassSheetClassIDRegexViolation"
    code: int = 5
    description: str = (
        "Class ID, which is stored in the column 'Class' in the 'Classes' sheet, "
        "does not respect defined regex expression"
    )
    example: str = (
        "If class id is set to 'Class 1', while regex expression does not allow spaces,"
        " the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check definition of class ids in 'Class' column in 'Classes' sheet and "
        "make sure to respect the regex expression by removing any illegal characters"
    )

    def __init__(self, class_id: str, regex_expression: str, verbose: bool = False):
        self.class_id = class_id
        self.regex_expression = regex_expression

        self.message = (
            f"Class id '{self.class_id}' stored in 'Class' column in 'Classes' "
            f"sheet violates regex {self.regex_expression}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ClassIDMissing(NeatException):
    """Class ID, which is stored in the column 'Class' in the 'Classes' sheet, is either
    missing or did not satisfied regex expression

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Make sure that class id is provided and respects regex expression
    """

    type_: str = "ClassIDMissing"
    code: int = 6
    description: str = (
        "Class ID, which is stored in the column 'Class' in the 'Classes' sheet,"
        " is either missing or did not satisfied regex expression"
    )
    example: str = ""
    fix: str = "Make sure that class id is provided and respects regex expression"

    def __init__(self, verbose: bool = False):
        self.message = (
            "Class id is missing, it failed validation either because it has"
            " not been provided or because it did not respect regex expression!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertiesSheetClassIDRegexViolation(NeatException):
    """Class ID, which is stored in the column 'Class' in the 'Properties' sheet, does
    not respect defined regex expression

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False
        class_id: class id that raised exception
        regex_expression: regex expression against which class id is checked

    Notes:
        Check definition of class ids in `Class` column in `Properties` sheet and make
        sure to respect the regex expression by removing any illegal characters
    """

    type_: str = "PropertiesSheetClassIDRegexViolation"
    code: int = 7
    description: str = (
        "Class ID, which is stored in the column 'Class' in the 'Properties' sheet, "
        "does not respect defined regex expression"
    )
    example: str = (
        "If class id is set to 'Class 1', while regex expression does not allow spaces,"
        " the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check definition of class ids in 'Class' column in 'Properties' sheet "
        "and make sure to respect the regex expression by removing any illegal characters"
    )

    def __init__(self, class_id: str, regex_expression: str, verbose: bool = False):
        self.class_id = class_id
        self.regex_expression = regex_expression

        self.message = (
            f"Class id '{self.class_id}' stored in 'Class' column in 'Properties' "
            f"sheet violates regex {self.regex_expression}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertyIDRegexViolation(NeatException):
    """Property ID, which is stored in the column 'Property' in the 'Properties' sheet, does
    not respect defined regex expression

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False
        property_id: property id that raised exception
        regex_expression: regex expression against which property id is checked

    Notes:
        Check definition of class ids in `Property` column in `Properties` sheet and make
        sure to respect the regex expression by removing any illegal characters
    """

    type_: str = "PropertyIDRegexViolation"
    code: int = 8
    description: str = (
        "Property ID, which is stored in the column 'Property' "
        "in the 'Properties' sheet, does not respect defined regex expression"
    )
    example: str = (
        "If property id is set to 'property 1', while regex expression does not allow spaces,"
        " the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check definition of property ids in 'Property' column in 'Properties' sheet"
        " and make sure to respect the regex expression by removing any illegal characters"
    )

    def __init__(self, property_id: str, regex_expression: str, verbose: bool = False):
        self.property_id = property_id
        self.regex_expression = regex_expression

        self.message = (
            f"Property id '{self.property_id}' stored in 'Property' "
            f"column in 'Properties' sheet violates regex {self.regex_expression}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ValueTypeIDRegexViolation(NeatException):
    """Value type, which is stored in the column 'Type' in the 'Properties' sheet, does
    not respect defined regex expression

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False
        value_type: value type that raised exception
        regex_expression: regex expression against which value type is checked

    Notes:
        Check definition of class ids in `Type` column in `Properties` sheet and make
        sure to respect the regex expression by removing any illegal characters
    """

    type_: str = "ValueTypeIDRegexViolation"
    code: int = 9
    description: str = (
        "Value type, which is stored in the column 'Type' in the 'Properties' sheet, "
        "does not respect defined regex expression"
    )
    example: str = (
        "If value type is set to 'date time', while regex expression does not"
        " allow spaces, the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check definition of value types in 'Type' column in 'Properties' sheet"
        " and make sure to respect the regex expression by removing any illegal characters"
    )

    def __init__(self, value_type: str, regex_expression: str, verbose: bool = False):
        self.value_type = value_type
        self.regex_expression = regex_expression

        self.message = (
            f"Value type '{self.value_type}' stored in 'Type' column in "
            f"'Properties' sheet violates regex {self.regex_expression}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class MissingTypeValue(NeatException):
    """Value type, which is stored in the column 'Type' in the 'Properties' sheet, is missing

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Make sure to define value type in `Type` column in `Properties` sheet
    """

    type_: str = "MissingTypeValue"
    code: int = 10
    description: str = "Value type, which is stored in the column 'Type' in the 'Properties' sheet, is missing"
    example: str = "If value type is not set, this error will be raised"
    fix: str = "Make sure to define value type in 'Type' column in 'Properties' sheet"

    def __init__(self, verbose: bool = False):
        self.message = (
            "Value type, which is stored in the column 'Type' in the 'Properties' sheet, is missing"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertyIDMissing(NeatException):
    """Property ID, which is stored in the column 'Property' in the 'Properties' sheet,
    is either missing or did not satisfied regex expression

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Make sure to define value type in `Type` column in `Properties` sheet
    """

    type_: str = "PropertyIDMissing"
    code: int = 11
    description: str = (
        "Property ID, which is stored in the column 'Property' in the 'Properties' sheet,"
        " is either missing or did not satisfied regex expression"
    )
    example: str = ""
    fix: str = "Make sure that property id is provided and respects regex expression"

    def __init__(self, verbose: bool = False):
        self.message = (
            "Property id is missing, validator for property id failed either"
            " due to lack of property id or due to not respecting regex expression!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class RuleTypeProvidedButRuleMissing(NeatException):
    """This error occurs when transformation rule type is provided but actual
    transformation rule is missing

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False
        property_id: property id which is missing transformation rule
        class_id: class id for which property id is defined
        rule_type: rule type that is provided for property id

    Notes:
        If you provide rule type you must provide rule as well! Otherwise remove rule
        type if no transformation rule is needed
    """

    type_: str = "RuleTypeProvidedButRuleMissing"
    code: int = 12
    description: str = (
        "This error occurs when transformation rule type is provided but actual transformation rule is missing"
    )
    example: str = ""
    fix: str = (
        "If you provide rule type you must provide rule as well! "
        "Otherwise remove rule type if no transformation rule is needed"
    )

    def __init__(self, property_id: str, class_id: str, rule_type: str, verbose: bool = False):
        self.message = (
            f"Rule type '{rule_type}' provided for property '{property_id}' "
            f"in class '{class_id}' but rule is not provided!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertyDefinedForUndefinedClass(NeatException):
    """Property defined for a class that has not been defined in the 'Classes' sheet

    Args:
        property_id: property id that is defined for undefined class
        class_id: class id that is undefined
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Make sure to define all classes in the 'Classes' sheet before defining properties
        for them in the `Properties` sheet
    """

    type_: str = "PropertyDefinedForUndefinedClass"
    code: int = 13
    description: str = "Property defined for a class that has not been defined in the 'Classes' sheet"
    example: str = (
        "If property 'someProperty' is defined for class 'Class 1' in the 'Properties' sheet, "
        "while 'Class 1' has not been defined in the 'Classes' sheet,"
        " this error will be raised"
    )
    fix: str = (
        "Make sure to define all classes in the 'Classes' sheet before defining properties for them"
        " in the 'Properties' sheet"
    )

    def __init__(self, property_id: str, class_id: str, verbose: bool = False):
        self.property_id = property_id
        self.class_id = class_id

        self.message = (
            f"Class <{self.class_id}> to which property {self.property_id}> is being defined"
            " is not define in the 'Classes' sheet!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class MetadataSheetMissingOrFailedValidation(NeatException):
    """Metadata sheet is missing or it failed validation for one or more fields

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
       Make sure to define compliant Metadata sheet before proceeding
    """

    type_: str = "MetadataSheetMissingOrFailedValidation"
    code: int = 14
    description: str = "Metadata sheet is missing or it failed validation for one or more fields"
    example: str = ""
    fix: str = "Make sure to define compliant Metadata sheet before proceeding"

    def __init__(self, verbose: bool = False):
        self.message = (
            "Metadata sheet is missing or it failed validation for one or more fields!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class FiledInMetadataSheetMissingOrFailedValidation(NeatException):
    """One of the mandatory fields in Metadata sheet is missing or it failed validation

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
       Make sure to define compliant field in Metadata sheet before proceeding
    """

    type_: str = "FiledInMetadataSheetMissingOrFailedValidation"
    code: int = 15
    description: str = "One of the mandatory fields in Metadata sheet is missing or it failed validation"
    example: str = ""
    fix: str = "Make sure to define compliant field in Metadata sheet before proceeding"

    def __init__(self, missing_field: str, verbose: bool = False):
        self.message = (
            f"Field {missing_field} is missing in the 'Metadata' sheet or it failed validation!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PrefixesRegexViolation(NeatException):
    """Prefix(es), which are in the 'Prefixes' sheet, do(es) not respect defined regex expression

    Args:
        prefixes: list of prefixes that violate regex expression
        regex_expression: regex expression that is violated
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
       Check if prefixes in the `Prefixes` sheet contains any illegal characters and respects the regex expression
    """

    type_: str = "PrefixesRegexViolation"
    code: int = 16
    description: str = "Prefix(es), which are in the 'Prefixes' sheet, do(es) not respect defined regex expression"
    example: str = (
        "If prefix is set to 'power grid', while regex expression does not "
        "allow spaces, the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check if prefixes in the 'Prefixes' sheet contains any illegal characters and respects the regex expression"
    )

    def __init__(self, prefixes: list[str], regex_expression: str, verbose: bool = False):
        self.prefixes = prefixes
        self.regex_expression = regex_expression

        self.message = (
            f"Invalid prefix(es) {', '.join(self.prefixes)} stored in the 'Prefixes' sheet, "
            f"it/they must obey regex {self.regex_expression}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PrefixesSheetNamespaceNotValidURL(NeatException):
    """Namespace(es), which are/is in the 'Prefixes' sheet, are/is not valid URL(s)

    Args:
        namespaces: list of namespaces that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
       Check if `namespaces` in the `Prefixes` sheet are properly constructed as valid
       URLs containing only allowed characters
    """

    type_: str = "PrefixesSheetNamespaceNotValidURL"
    code: int = 17
    description: str = "Namespace(es), which are/is in the 'Prefixes' sheet, are/is not valid URLs"
    example: str = "If we have 'authority:namespace' as namespace as it is not a valid URL this error will be raised"
    fix: str = (
        "Check if 'namespaces' in the 'Prefixes' sheet are properly "
        "constructed as valid URLs containing only allowed characters"
    )

    def __init__(self, namespaces: list[str], verbose: bool = False):
        self.namespaces = namespaces

        self.message = (
            f"Invalid namespace(es) {', '.join(self.namespaces)} stored in the 'Prefixes' sheet, "
            f"it/they must be valid URLs!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ValueTypeNotDefinedAsClass(NeatException):
    """Expected value type, which is stored in the column 'Type' in the 'Properties' sheet,
    is not defined in the 'Classes' sheet. This error occurs when property is defined as
    an edge between two classes, of which one is not defined

    Args:
        expected_value_type: expected value type that raised exception
        property_id: property id that has expected value type that raised exception
        class_id: class id for which property is defined
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Make sure to define all of the classes in the `Classes` sheet before defining
        properties that expect them as value types
    """

    type_: str = "ValueTypeNotDefinedAsClass"
    code: int = 18
    description: str = (
        "Expected value type, which is stored in the column 'Type' in the 'Properties'"
        " sheet, is not defined in the 'Classes' sheet. "
        "This error occurs when property is defined as an edge between two classes, of which one is not defined"
    )
    example: str = (
        "We have 'Class1' which has property 'edgeClass1Class2' linking it to 'Class2', thus"
        "expected value of 'edgeClass1Class2' is 'Class2'. However, 'Classes' sheet only contains"
        " 'Class1', while 'Class2' is not defined. Under this given circumstance, this error will be raised!"
    )

    fix: str = (
        "Make sure to define all of the classes in the 'Classes' sheet before defining "
        "properties that expect them as value types"
    )

    def __init__(self, class_id: str, property_id: str, expected_value_type: str, verbose: bool = False):
        self.message = (
            f"Property {property_id} defined for class {class_id} has"
            f" value type {expected_value_type} which is not defined as a class in the 'Classes' sheet!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class UndefinedObjectsAsExpectedValueTypes(NeatException):
    """Expected value types, which are stored in the column 'Type' in the 'Properties'
    sheet, are classes that exist in the 'Classes' sheet but for which no properties are defined
    in the 'Properties' sheet.

    Args:
        undefined_objects: list of undefined objects that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Make sure to define properties for classes from 'Classes' sheet before defining
        properties that expect them as value types
    """

    type_: str = "UndefinedObjectsAsExpectedValueTypes"
    code: int = 19
    description: str = (
        "Expected value types, which are stored in the column 'Type' in the 'Properties'"
        " sheet, are classes that exist in the 'Classes' sheet but for which no properties are defined "
        "in the 'Properties' sheet. "
    )
    example: str = (
        "We have 'Class1' which has property 'edgeClass1Class2' linking it to 'Class2', thus"
        "expected value of 'edgeClass1Class2' is 'Class2'. "
        "Both 'Class1' and 'Class2' are defined in the 'Classes' sheet"
        "However, only 'Class1' has properties defined in the 'Properties' sheet, making 'Class2' an undefined object"
        " leading to this error being raised!"
    )

    fix: str = (
        "Make sure to define properties for classes from 'Classes' "
        "sheet before defining properties that expect them as value types"
    )

    def __init__(self, undefined_objects: list[str], verbose: bool = False):
        self.message = (
            f"Following classes {', '.join(undefined_objects)} defined as classes in the 'Classes' sheet"
            f" have no properties defined in the 'Properties' sheet or their validation as objects failed!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ClassSheetParentClassIDRegexViolation(NeatException):
    """Parent ID, which is stored in the column 'Parent Class' in the 'Classes' sheet,
    does not respect defined regex expression

    Args:
        parent_ids: parent_ids that raised exception
        regex_expression: regex expression against which parent_id is validated
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Check definition of parent ids in `Parent Class` column in `Classes` sheet and
        make sure to respect the regex expression by removing any illegal characters

    """

    type_: str = "ClassSheetParentClassIDRegexViolation"
    code: int = 20
    description: str = (
        "Parent ID, which is stored in the column 'Parent Class' in the 'Classes' sheet, "
        "does not respect defined regex expression"
    )
    example: str = (
        "If parent class is set to 'Class 1', while regex expression does not allow spaces,"
        " the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check definition of class ids in 'Parent Class' column in 'Classes' sheet and "
        "make sure to respect the regex expression by removing any illegal characters"
    )

    def __init__(self, parent_ids: list[str], regex_expression: str, verbose: bool = False):
        self.parent_ids = parent_ids
        self.regex_expression = regex_expression

        self.message = (
            f"Parents ids: [{', '.join(parent_ids or [])}], stored in 'Parent Class' column in 'Classes' "
            f"sheet violates regex {self.regex_expression}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class MoreThanOneNonAlphanumericCharacter(NeatException):
    """This exceptions is raised when doing regex validation of strings which either
    represent class ids, property ids, prefix, data model name, that contain more than
    one non-alphanumeric character, such as for example '_' or '-'.

    Args:
        field_name: filed on which regex validation failed
        value: value that failed regex validation
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Make sure not to use more than non-alphanumeric character in the row

    """

    type_: str = "MoreThanOneNonAlphanumericCharacter"
    code: int = 21
    description: str = (
        "This exceptions is raised when doing regex validation of strings which either"
        "represent class ids, property ids, prefix, data model name, that contain more than"
        "one non-alphanumeric character, such as for example '_' or '-'."
    )
    example: str = ""
    fix: str = ""

    def __init__(self, field_name: str, value: str, verbose: bool = False):
        self.field_name = field_name
        self.value = value

        self.message = (
            f"Field {field_name} with value {value} contains more than one non-alphanumeric character!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ViewExternalIdNotDefined(NeatException):
    """This exceptions is raised when external id of View is not defined.

    Args:
        field_name: filed on which regex validation failed
        value: value that failed regex validation
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    """

    type_: str = "ViewExternalIdNotDefined"
    code: int = 22
    description: str = "This exceptions is raised when external id of View is not defined"
    example: str = ""
    fix: str = ""

    def __init__(self, verbose: bool = False):
        self.message = (
            f"Missing View external id!" f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class SpaceNotDefined(NeatException):
    """This exceptions is raised when CDF space name is missing.

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    """

    type_: str = "SpaceNotDefined"
    code: int = 23
    description: str = "This exceptions is raised when CDF space name is missing"
    example: str = ""
    fix: str = ""

    def __init__(self, verbose: bool = False):
        self.message = (
            f"Missing CDF space name!" f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ViewVersionNotDefined(NeatException):
    """This exceptions is raised when View version is not provided.

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    """

    type_: str = "ViewVersionNotDefined"
    code: int = 24
    description: str = "This exceptions is raised when View version is not provided"
    example: str = ""
    fix: str = ""

    def __init__(self, verbose: bool = False):
        self.message = (
            f"Missing View version!" f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class DefaultValueTypeNotProper(NeatException):
    """This exceptions is raised when default value type is not proper, i.e. it is not
    according to the expected value type set in Rules.


    Args:
        default_value_type: default value type that raised exception
        expected_value_type: expected value type that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    """

    type_: str = "DefaultValueTypeNotProper"
    code: int = 25
    description: str = (
        "This exceptions is raised when default value type is not proper, i.e. it is not "
        "according to the expected value type set in Rules."
    )
    example: str = ""
    fix: str = ""

    def __init__(self, property_id: str, default_value_type: str, expected_value_type: str, verbose: bool = False):
        self.default_value_type = default_value_type
        self.expected_value_type = expected_value_type

        self.message = (
            f"Default value for property {property_id} is of type {default_value_type} which is different from "
            f"the expected value type {expected_value_type}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ClassToAssetMappingNotDefined(NeatException):
    """This exceptions is raised when deriving class to asset mapping when there is no
    mapping available.


    Args:
        class_id: Id of the class that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    """

    type_: str = "ClassToAssetMappingNotDefined"
    code: int = 26
    description: str = (
        "This exceptions is raised when deriving class to asset mapping when there is no mapping available"
    )
    example: str = ""
    fix: str = ""

    def __init__(self, class_id: str, verbose: bool = False):
        self.class_id = class_id

        self.message = (
            f"Requested serialization from pydantic model instance of class {class_id} is"
            " not possible since there is no class to asset mapping available!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PrefixAlreadyInUse(NeatException):
    """This exceptions is raised when trying to update base prefix/space of Rules object


    Args:
        class_id: Id of the class that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    """

    type_: str = "PrefixAlreadyInUse"
    code: int = 27
    description: str = "This exceptions is raised when trying to update base prefix/space of Rules object"
    example: str = ""
    fix: str = ""

    def __init__(self, prefix: str, verbose: bool = False):
        self.prefix = prefix

        self.message = (
            f"Prefix {prefix} exist in self.prefixes, please use another prefix!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class IncompleteSchema(NeatException):
    """This exceptions is raised when schema is not complete, meaning defined properties
    are pointing to non-existing classes or value types


    Args:
        missing_classes: list of classes ids that are not defined in the sheet
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    """

    type_: str = "IncompleteSchema"
    code: int = 28
    description: str = (
        "This exceptions is raised when schema is not complete, meaning "
        "defined properties are pointing to non-existing classes or value types"
    )
    example: str = ""
    fix: str = ""

    def __init__(self, missing_classes: set, verbose: bool = False):
        self.message = (
            f"Classes {missing_classes} are not defined in the Class sheet!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


# Warnings:


class ClassNameNotProvided(NeatWarning):
    """This warning is raised when class name is not provided in the 'Classes' sheet
    under 'name' column, which will be then set the class id stored in the 'Class' column

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False
        class_id: class id that raised warning, and which is used as class name

    Notes:
        If you want to have differentiation between the class name and class id, then
        provide class name in the `name` column
    """

    type_: str = "ClassNameNotProvided"
    code: int = 1
    description: str = (
        "This warning is raised when class name is not provided in the 'Classes' sheet"
        "under 'name' column, which will be then set the class id stored in the 'Class' column"
    )
    example: str = ""
    fix: str = (
        "If you want to have differentiation between the class name"
        " and class id, then provide class name in the `name` column"
    )

    # need to have default value set to arguments
    # otherwise it will raise TypeError
    def __init__(self, class_id: str = "", verbose: bool = False):
        self.message = (
            f"Class id {class_id} set as Class name!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class EntityIDNotDMSCompliant(NeatWarning):
    """Warning raise when entity id being class, property or value type is not DMS compliant

    Args:
        entity_type: type of entity that raised warning
        entity_id: id of entity that raised warning
        loc: location of entity in the Transformation Rules sheet that raised warning
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        DMS ready means that entity id must only use following characters [a-zA-Z0-9_],
        where it can only start with letter! Also there are reserved words that cannot be used.

        Reserved words for views: `Query`, `Mutation`, `Subscription`, `String`, `Int32`, `Int64`, `Int`,
        `Float32`, `Float64`, `Float`, `Timestamp`, `JSONObject`, `Date`, `Numeric`, `Boolean`, `PageInfo`,
        `File`, `Sequence`, `TimeSeries`

        Reserved words for properties: `space`, `externalId`, `createdTime`, `lastUpdatedTime`,
        `deletedTime`, `edge_id`, `node_id`, `project_id`, `property_group`, `seq`, `tg_table_name`, `extensions`

        Reserved words for spaces: `space`, `cdf`, `dms`, `pg3`, `shared`, `system`, `node`, `edge`
    """

    type_: str = "EntityIDNotDMSCompliant"
    code: int = 2
    description: str = "Warning raise when entity id being class, property or value type is not DMS compliant"
    example: str = ""
    fix: str = (
        "DMS ready means that entity id must only use following"
        " characters [a-zA-Z0-9_], where it can only start with letter!"
    )

    # See ClassNameNotProvided for explanation why default values are set
    def __init__(self, entity_type: str = "", entity_id: str = "", loc: str = "", verbose: bool = False):
        self.message = (
            f"'{entity_id}' {entity_type.lower()}"
            " use character(s) outside of range of allowed characters [a-zA-Z0-9_] or "
            f"it starts with non-letter character or it is reserved word! {loc}"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class PropertyRedefined(NeatWarning):
    """Warning raise when same property is defined multiple times for same class, this
    typically occurs if there are multiple ways to extract certain information from the
    NeatGraph.

    Args:
        property_id: property id that is redefined
        class_id: class id for which property is redefined
        loc: location of property redefinition in the 'Properties' sheet of Transformation Rules Excel file
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        If possible, have only single definition of a particular property for a class, otherwise
        transformation rules will not be DMS compliant.
    """

    type_: str = "PropertyRedefined"
    code: int = 3
    description: str = "Warning raise when same property is defined multiple times for same class"
    example: str = ""
    fix: str = "Have only single definition of a particular property for a class"

    # See Warning302 for explanation why default values are set
    def __init__(self, property_id: str = "", class_id: str = "", loc: str = "", verbose: bool = False):
        self.message = (
            f"Not DMS compliant! Property '{property_id}' for class '{class_id}' redefined! {loc}"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page


class PropertyNameNotProvided(NeatWarning):
    """If property name is not provided in the 'Property' sheet under 'name' column, it
    will be set to corresponding value from 'Property' column, thus property id

    Args:
        property_id: property id that is set as property name
        verbose: flag that indicates whether to provide enhanced exception message, by default False
    Notes:
        If you want to have different property name then property id, provide it in the 'name' column
    """

    type_: str = "PropertyNameNotProvided"
    code: int = 4
    description: str = (
        "If property name is not provided in the 'Property' sheet under 'name' column,"
        " it will be set to corresponding value from 'Property' column, thus property id"
    )
    example: str = ""
    fix: str = "If you want to have different property name then property id, provide it in the 'name' column"

    def __init__(self, property_id: str = "", verbose: bool = False):
        self.message = (
            f"Property id {property_id} set as Property name!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class MissingLabel(NeatWarning):
    """If property maps to CDF relationship, and it does not have label explicitly stated
    under 'Label' column  in the 'Property' sheet under 'name' column,  it will be set
    to corresponding value from 'Property' column, thus property id

    Args:
        property_id: property id that which is missing label
        verbose: flag that indicates whether to provide enhanced exception message, by default False


    Notes:
        If you want to have control over relationship labels make sure to define one
        in the `Label` column in the `Properties` sheet
    """

    type_: str = "MissingLabel"
    code: int = 5
    description: str = (
        "If property maps to CDF relationship, and it does not have label explicitly stated under 'Label' column"
        " in the 'Property' sheet under 'name' column,"
        " it will be set to corresponding value from 'Property' column, thus property id"
    )
    example: str = ""
    fix: str = (
        "If you want to have control over relationship labels make sure to define one"
        " in the 'Label' column in the 'Properties' sheet."
    )

    def __init__(self, property_id: str = "", verbose: bool = False):
        self.message = (
            f"Property id {property_id} set as CDF relationship label!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class NoTransformationRules(NeatWarning):
    """This warning is raised if there are no transformation rules defined for given
    property and class

    Args:
        property_id: property id that which is missing transformation rules
        class_id: class id for which property is missing transformation rules
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        One can omit this warning if the Transformation Rules spreadsheet is used solely
        for defining the data model and not for performing knowledge graph transformation.
    """

    type_: str = "NoTransformationRules"
    code: int = 6
    description: str = (
        "This warning is raised if there are no transformation rules "
        "defined in the 'Transformation' sheet for given property"
    )
    example: str = ""
    fix: str = "No fix is provided for this warning"

    def __init__(self, property_id: str = "", class_id: str = "", verbose: bool = False):
        self.message = (
            f"There is no transformation rule configured for class '{class_id}' property '{property_id}'!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class NamespaceEndingFixed(NeatWarning):
    """This warning occurs when namespace does not end with '/' or '#'

    Args:
        namespace: namespace that raised warning due to improper ending
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Make sure that namespace ends with `/` or `#`, if not it will be fixed by adding
        `#` at the end !
    """

    type_: str = "NamespaceEndingFixed"
    code: int = 7
    description: str = "This warning occurs when namespace does not end with '/' or '#'"
    example: str = "If namespace is set to http://purl.org/cognite, it will be converted to http://purl.org/cognite#"
    fix: str = "Make sure that namespace ends with '/' or '#'"

    def __init__(self, namespace: Namespace, verbose: bool = False):
        self.message = (
            f"Namespace {namespace} ending fixed by adding '#' at its end!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page


class DataModelIdMissing(NeatWarning):
    """This warning occurs when data model name is not provided in 'Metadata' sheet

    Args:
        prefix: prefix to which data model name will be set if not provided
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Make sure that namespace ends with `/` or `#`, if not it will be fixed by adding
        `#` at the end !
    """

    type_: str = "DataModelIdMissing"
    code: int = 8
    description: str = "This warning occurs when data model id is not provided in 'Metadata' sheet"
    example: str = ""
    fix: str = (
        "Provide data model id by setting value for `external_id`,"
        " to avoid this warning and otherwise it will default to prefix"
    )

    def __init__(self, prefix: str, verbose: bool = False):
        self.message = (
            f"Data model id not provided, defaulting to prefix {prefix}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class VersionDotsConvertedToUnderscores(NeatWarning):
    """This warning occurs when converting version from dot notation to use of underscores
    in order to achieve version format that is accepted by CDF/DMS

    Args:
        prefix: prefix to which data model name will be set if not provided
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Typically version is expressed in classical form with dots major.minor.patch, while
        CDF accepts underscores major_minor_patch, thus this warning occurs when converting
        version from dot notation to use of underscores in order to achieve version format
        that is accepted by CDF/DMS
    """

    type_: str = "VersionDotsConvertedToUnderscores"
    code: int = 9
    description: str = (
        "This warning occurs when converting version from dot notation to use of underscores"
        " in order to achieve version format that is accepted by CDF/DMS"
    )
    example: str = "If version is provided as 1.2.3, this will be converted to 1_2_3 to be accepted by CDF"
    fix: str = "Convert version to underscore notation major_minor_patch"

    def __init__(self, verbose: bool = False):
        self.message = (
            "Data model version expressed with '.' which is not acceptable for CDF."
            " All '.' are converted to '_'!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page


class DefaultValueTypeConverted(NeatWarning):
    """This exceptions is warning is raised when default value type is being converted to
    the expected value type set in Rules.


    Args:
        default_value_type: default value type that raised exception
        expected_value_type: expected value type that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Make sure not to use more than non-alphanumeric character in the row

    """

    type_: str = "DefaultValueTypeConverted"
    code: int = 10
    description: str = (
        "This exceptions is warning is raised when default value type is being converted to "
        "the expected value type set in Rules."
    )
    example: str = ""
    fix: str = ""

    def __init__(
        self, property_id: str = "", default_value_type: str = "", expected_value_type: str = "", verbose: bool = False
    ):
        self.default_value_type = default_value_type
        self.expected_value_type = expected_value_type

        self.message = (
            f"Default value for property {property_id} is of type {default_value_type} "
            f"has been converted to the expected value type {expected_value_type}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class DefaultValueNotList(NeatWarning):
    """This exceptions is warning is raised when default value is not a list while it is
    expected to be due to set maximum cardinality being different than 1.


    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Make sure not to use more than non-alphanumeric character in the row

    """

    type_: str = "DefaultValueNotList"
    code: int = 11
    description: str = (
        "This exceptions is warning is raised when default value is not a list while it is "
        "expected to be due to set maximum cardinality being different than 1"
    )
    example: str = ""
    fix: str = ""

    def __init__(self, property_id: str, verbose: bool = False):
        self.message = (
            f"Default value for property {property_id} is not a list, "
            "while it is expected to be due to set maximum cardinality being different than 1!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


################################################################################################
# RULES PROCESSING: 100 - 199 ##################################################################
################################################################################################


class NotValidRDFPath(NeatException):
    """Provided `rdfpath` is not valid, i.e. it cannot be converted to SPARQL query.

    Args:
        rdf_path: `rdfpath` that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Get familiar with `rdfpath` to avoid this exception.
    """

    type_: str = "NotValidRDFPath"
    code: int = 100
    description: str = "Provided `rdfpath` is not valid, i.e. it cannot be converted to SPARQL query"
    example: str = ""
    fix: str = "Get familiar with `rdfpath` and check if provided path is valid!"

    def __init__(self, rdf_path: str, verbose: bool = False):
        self.rdf_path = rdf_path

        self.message = (
            f"{self.rdf_path} is not a valid rdfpath!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class NotValidTableLookUp(NeatException):
    """Provided `table lookup` is not valid, i.e. it cannot be converted to CDF lookup.

    Args:
        table_look_up: `table_look_up`, a part of `rawlookup`, that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Get familiar with `rawlookup` and `rdfpath` to avoid this exception.
    """

    type_: str = "NotValidTableLookUp"
    code: int = 101
    description: str = "Provided table lookup is not valid, i.e. it cannot be converted to CDF lookup"
    example: str = ""
    fix: str = "Get familiar with RAW look up and RDF paths and check if provided rawlookup is valid"

    def __init__(self, table_look_up: str, verbose: bool = False):
        self.table_look_up = table_look_up

        self.message = (
            f"{self.table_look_up} is not a valid table lookup"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class NotValidRAWLookUp(NeatException):
    """Provided `rawlookup` is not valid, i.e. it cannot be converted to SPARQL query and CDF lookup

    Args:
        raw_look_up: `rawlookup` rule that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Get familiar with `rawlookup` and `rdfpath` to avoid this exception.
    """

    type_: str = "NotValidRAWLookUp"
    code: int = 102
    description: str = "Provided rawlookup is not valid, i.e. it cannot be converted to SPARQL query and CDF lookup"
    example: str = ""
    fix: str = "Get familiar with `rawlookup` and `rdfpath` to avoid this exception"

    def __init__(self, raw_look_up: str, verbose: bool = False):
        self.raw_look_up = raw_look_up

        self.message = (
            f"Invalid rawlookup expected traversal | table lookup, got {raw_look_up}"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


################################################################################################
# RULES IMPORTERS: 200 - 299 ###################################################################
################################################################################################
class RulesHasErrors(NeatWarning):
    """This warning occurs when generated transformation rules are invalid/incomplete.

    Args:
        importer_type: type of importer that is used to generate transformation rules
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Generated transformation rules are not guaranteed to be valid and complete.
        Go through the generated report file and fix the errors and warnings.
    """

    type_: str = "GeneratedTransformationRulesHasErrors"
    code: int = 200
    description: str = (
        "This warning occurs when transformation rules generated using an importer are invalid/incomplete."
    )
    example: str = ""
    fix: str = "Go through the generated report file and fix the warnings in generated Transformation Rules."

    def __init__(self, importer_type: str = "OWL ontology", verbose: bool = False):
        self.message = (
            f"Rules generated using {importer_type} are invalid!"
            " Consult generated validation report for details on the errors and fix them"
            " before using the rules file."
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class RulesHasWarnings(NeatWarning):
    """This warning occurs when th generated transformation rules are invalid/incomplete.

    Args:
    importer_type: type of importer that is used to generate transformation rules
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        OWL ontology is not guaranteed to contain all information needed to generate
        transformation rules. In such cases, transformation rules generated from OWL ontology
        will be incomplete and invalid. Go through the generated report file and fix the warnings
    """

    type_: str = "GeneratedTransformationRulesHasWarnings"
    code: int = 201
    description: str = (
        "This warning occurs when transformation rules generated using an importer are invalid/incomplete."
    )
    example: str = ""
    fix: str = "Go through the generated report file and fix the warnings in generated Transformation Rules."

    def __init__(self, importer_type: str = "OWL ontology", verbose: bool = False):
        self.message = (
            f"Rules generated using {importer_type} raised warnings!"
            " Consult generated validation report for details on the warnings and optionally fix them"
            " before using the rules file."
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class GraphClassNameCollision(NeatWarning):
    """This warning occurs when graph contains instances of classes with same name, but
    belonging to different namespaces.

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Since the RDF graph is fully flexible and based on URIs, it is possible to have
        instances of classes with same name, but belonging to different namespaces. This
        warning is raised when such collision occurs.
    """

    type_: str = "GraphClassNameCollision"
    code: int = 202
    description: str = (
        "This warning occurs when graph contains instances of classes with same name, but"
        " belonging to different namespaces."
    )
    example: str = ""
    fix: str = "Be caution when reviewing the generated transformation rules."

    def __init__(self, class_name: str, verbose: bool = False):
        self.message = f"Class name collision detected in the graph for class name {class_name}!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class GraphClassPropertyMultiValueTypes(NeatWarning):
    """This warning occurs when a same property is define for two object/classes where
    its expected value type is different in one definition, e.g. acts as an edge, while in
    other definition acts as and attribute

    Args:
        class_id: class id that raised warning due to multi type definition
        property_id: property id that raised warning due to multi type definition
        types: list of types of property
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        If a property takes different value types for different objects, simply define
        new property. It is bad practice to have multi type property!
    """

    type_: str = "GraphClassPropertyMultiValueTypes"
    code: int = 203
    description: str = (
        "This warning occurs when a same property is define for two object/classes where"
        " its expected value type is different in one definition, e.g. acts as an edge, while in "
        "other definition acts as and attribute"
    )
    example: str = ""
    fix: str = "If a property takes different value types for different objects, simply define new property"

    def __init__(
        self, class_name: str = "", property_name: str = "", types: list[str] | None = None, verbose: bool = False
    ):
        self.message = (
            "It is bad practice to have multi type property! "
            f"Currently property '{property_name}' for class {class_name} has"
            f" multi type property: {', '.join(types or [])}"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class GraphClassPropertyMultiOccurrence(NeatWarning):
    """This warning occurs when there is multiple different occurrences of the same property
    across various class instances.

    Args:
        class_id: class id that raised warning due to multi type definition
        property_id: property id that raised warning due to multi type definition
        occurrences: list of property occurrences
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        If a property takes different value types for different objects, simply define
        new property. It is bad practice to have multi type property!
    """

    type_: str = "GraphClassPropertyMultiOccurrence"
    code: int = 204
    description: str = (
        "This warning occurs when there is multiple different occurrences of the same property "
        " across various class instances"
    )
    example: str = ""
    fix: str = "There"

    def __init__(self, class_name: str = "", property_name: str = "", verbose: bool = False):
        self.message = (
            f"Currently property '{property_name}' for class {class_name} has multi occurrences"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


################################################################################################
# RULES PARSERS: 300 - 399 #####################################################################
################################################################################################
class SourceObjectDoesNotProduceMandatorySheets(NeatException):
    """Given object (e.g., Excel file) does not produce one or more mandatory sheets

    Args:
        missing_mandatory_sheets: set of missing mandatory sheets
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        This exception is raised when source object converted to is missing one or more mandatory sheets.
        The mandatory sheets are: `Metadata`, `Classes`, `Properties`.
    """

    type_: str = "SourceObjectDoesProduceMandatorySheets"
    code: int = 300
    description: str = "Given Excel file is missing one or more mandatory sheets"
    example: str = "An Excel file is missing sheet named 'Metadata'"
    fix: str = "Make sure that Excel file contains all mandatory sheets, i.e. 'Metadata', 'Classes', 'Properties'"

    def __init__(self, missing_mandatory_sheets: set[str], verbose: bool = False):
        self.missing_fields = missing_mandatory_sheets

        self.message = (
            "Given Excel file is not compliant Transformation Rules file."
            f" It is missing mandatory sheets: {', '.join(missing_mandatory_sheets)}."
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class UnableToDownloadExcelFile(NeatException):
    """This error is raised during loading of byte representation of  a Excel file from
    Github, when given file cannot be downloaded.

    Args:
        filepath: file path to Excel file that cannot be downloaded from Github
        loc: URL of Excel file from Github repository
        reason: reason why file cannot be downloaded (e.g., Forbidden, Not Found, etc.)
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
       Make sure you provided correct parameters to download Excel file from github repository.
    """

    type_: str = "UnableToDownloadExcelFile"
    code: int = 301
    description: str = (
        "This error is raised during loading of byte representation of"
        " a Excel file from Github when given file cannot be downloaded."
    )
    example: str = ""
    fix: str = "Make sure you provided correct parameters to download Excel file from github repository"

    def __init__(self, filepath: str, loc: str, reason: str, verbose: bool = False):
        self.message = (
            f"File '{filepath}' from '{loc}' cannot be downloaded! Reason: {reason}"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class NotExcelFile(NeatException):
    """This error is raised during loading of byte representation of a file from Github
    into `openpyxl` `Workbook` object in case when byte representation is not Excel file.

    Args:
        filepath: file path to Excel file that cannot be downloaded from Github
        loc: URL of Excel file from Github repository
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
       Make sure you that byte representation of a file is Excel file.
    """

    type_: str = "NotExcelFile"
    code: int = 302
    description: str = (
        "This error is raised during loading of byte representation of a file from Github"
        " into `openpyxl` `Workbook` object in case when byte representation is not Excel file."
    )
    example: str = ""
    fix: str = "Make sure you that byte representation of a file is Excel file!"

    def __init__(self, filepath: str, loc: str, verbose: bool = False):
        self.message = (
            f"File '{filepath}' from '{loc}' is not a valid excel file!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class MetadataSheetMissingMandatoryFields(NeatException):
    """Metadata sheet, which is part of Transformation Rules Excel file, is missing
    mandatory rows (i.e., fields)

    Args:
        missing_fields: Fields/rows that are missing in Metadata sheet
        verbose: flag that indicates whether to provide enhanced exception message, by default False
    """

    type_: str = "MetadataSheetMissingMandatoryFields"
    code: int = 303
    description: str = "Metadata sheet, which is part of Transformation Rules Excel file, is missing mandatory rows"
    example: str = ""
    fix: str = ""

    def __init__(self, missing_fields: set[str], verbose: bool = False):
        self.missing_fields = missing_fields

        self.message = (
            f"Metadata sheet is missing following mandatory fields: {', '.join(missing_fields)}"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ClassesSheetMissingMandatoryColumns(NeatException):
    """Classes sheet, which is a mandatory part of Transformation Rules Excel file, is
    missing mandatory columns at row 2

    Args:
        missing_fields: Fields/columns that are missing in Classes sheet
        verbose: flag that indicates whether to provide enhanced exception message, by default False
    """

    type_: str = "ClassesSheetMissingMandatoryColumns"
    code: int = 304
    description: str = (
        "Classes sheet, which is a mandatory part of Transformation Rules Excel file, "
        "is missing mandatory columns at row 2"
    )
    example: str = ""
    fix: str = ""

    def __init__(self, missing_fields: set[str], verbose: bool = False):
        self.missing_fields = missing_fields

        self.message = (
            f"Classes sheet is missing following mandatory columns: {', '.join(missing_fields)} at row 2"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertiesSheetMissingMandatoryColumns(NeatException):
    """Properties sheet, which is a mandatory part of Transformation Rules Excel file, is
    missing mandatory columns at row 2

    Args:
        missing_fields: Fields/columns that are missing in Properties sheet
        verbose: flag that indicates whether to provide enhanced exception message, by default False
    """

    type_: str = "PropertiesSheetMissingMandatoryColumns"
    code: int = 305
    description: str = (
        "Properties sheet, which is a mandatory part of Transformation Rules Excel file, "
        "is missing mandatory columns at row 2"
    )
    example: str = ""
    fix: str = ""

    def __init__(self, missing_fields: set[str], verbose: bool = False):
        self.missing_fields = missing_fields

        self.message = (
            f"Properties sheet is missing following mandatory columns: {', '.join(missing_fields)} at row 2"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PrefixesSheetMissingMandatoryColumns(NeatException):
    """Prefixes sheet, which is part of Transformation Rules Excel file, is missing
    mandatory columns at row 1

    Args:
        missing_fields: Fields/columns that are missing in Prefixes sheet
        verbose: flag that indicates whether to provide enhanced exception message, by default False
    """

    type_: str = "PrefixesSheetMissingMandatoryColumns"
    code: int = 306
    description: str = (
        "Prefixes sheet, which is part of Transformation Rules Excel file, is missing mandatory columns at row 1"
    )
    example: str = ""
    fix: str = ""

    def __init__(self, missing_fields: set[str], verbose: bool = False):
        self.missing_fields = missing_fields

        self.message = (
            f"Prefixes sheet is missing following mandatory columns: {', '.join(missing_fields)} at row 1"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class InstancesSheetMissingMandatoryColumns(NeatException):
    """Instances sheet, which is part of Transformation Rules Excel file, is missing
    mandatory columns at row 1

    Args:
        missing_fields: Fields/columns that are missing in Instances sheet
        verbose: flag that indicates whether to provide enhanced exception message, by default False
    """

    type_: str = "InstancesSheetMissingMandatoryColumns"
    code: int = 307
    description: str = (
        "Instances sheet, which is part of Transformation Rules Excel file, is missing mandatory columns at row 1"
    )
    example: str = ""
    fix: str = ""

    def __init__(self, missing_fields: set[str], verbose: bool = False):
        self.missing_fields = missing_fields

        self.message = (
            f"Instances sheet is missing following mandatory columns: {', '.join(missing_fields)} at row 1"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


# Warnings
class MissingDataModelPrefixOrNamespace(NeatWarning):
    """Prefix and/or namespace are missing in the 'Metadata' sheet

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
    Add missing prefix and/or namespace in the 'Metadata' sheet
    """

    type_: str = "MissingDataModelPrefixOrNamespace"
    code: int = 300
    description: str = "Either prefix or namespace or both are missing in the 'Metadata' sheet"
    example: str = ""
    fix: str = "Add missing prefix and/or namespace in the 'Metadata' sheet"

    def __init__(self, verbose: bool = False):
        self.message = (
            "Instances sheet is present but prefix and/or namespace are missing in 'Metadata' sheet."
            "Instances sheet will not be processed!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page


################################################################################################
# RULES EXPORTERS 400-499#######################################################################
################################################################################################


class EntitiesContainNonDMSCompliantCharacters(NeatException):
    """This error is raised during export of Transformation Rules to DMS schema when
    entities (e.g., types and fields) ids contain non DMS compliant characters.

    Args:
        report: report of entities that contain non DMS compliant characters
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
       Make sure to check validation report of Transformation Rules and fix DMS related exceptions.
    """

    type_: str = "EntitiesContainNonDMSCompliantCharacters"
    code: int = 400
    description: str = (
        "This error is raised during export of Transformation Rules to"
        " DMS schema when entities contain non DMS compliant characters."
    )
    example: str = ""
    fix: str = "Make sure to check validation report of Transformation Rules and fix DMS related exceptions."

    def __init__(self, report: str = "", verbose: bool = False):
        self.message = (
            f"Following entities contain non DMS compliant characters: {report}"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertiesDefinedMultipleTimes(NeatException):
    """This error is raised during export of Transformation Rules to DMS schema when
    when properties are defined multiple times for the same class.

    Args:
        report: report on properties which are defined multiple times
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
       Make sure to check validation report of Transformation Rules and fix DMS related warnings.
    """

    type_: str = "PropertiesDefinedMultipleTimes"
    code: int = 401
    description: str = (
        "This error is raised during export of Transformation Rules to "
        "DMS schema when properties are defined multiple times for the same class."
    )
    example: str = ""
    fix: str = "Make sure to check validation report of Transformation Rules and fix DMS related warnings."

    def __init__(self, report: str = "", verbose: bool = False):
        self.message = (
            f"Following properties defined multiple times for the same class(es): {report}"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertyDefinitionsNotForSameProperty(NeatException):
    """This error is raised if property definitions are not for linked to the same
    property id when exporting rules to ontological representation.

    Args:
        verbose: flag that indicates whether to provide enhanced exception message, by default False
    """

    type_: str = "PropertyDefinitionsNotForSameProperty"
    code: int = 402
    description: str = "This error is raised if property definitions are not for linked to the same property id"
    example: str = ""
    fix: str = ""

    def __init__(self, verbose: bool = False):
        self.message = (
            "All definitions should have the same property_id! Aborting."
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class FieldValueOfUnknownType(NeatException):
    """This error is raised when generating in-memory pydantic model from Transformation
    Rules from model, when field definitions are not provided as dictionary of field names
    ('str') and their types ('tuple' or 'dict').

    Args:
        field: field name that raised exception due to unknown type
        definition: definition of field that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False
    """

    type_: str = "FieldValueOfUnknownType"
    code: int = 403
    description: str = (
        "This error is raised when generating in-memory pydantic model"
        " from Transformation Rules from model, when field definitions are not"
        " provided as dictionary of field names ('str') and their types ('tuple' or 'dict')."
    )
    example: str = ""
    fix: str = ""

    def __init__(self, field: str, definition: Any, verbose: bool = False):
        self.message = (
            f"Field {field} has definition of type {type(definition)}"
            " which is not acceptable! Only definition in form of dict or tuple is acceptable!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class MissingInstanceTriples(NeatException):
    """This error is raised when queried RDF class instance does not return any triples that define it.

    Args:
        id_: instance id
        verbose: flag that indicates whether to provide enhanced exception message, by default False
    """

    type_: str = "MissingInstanceTriples"
    code: int = 404
    description: str = (
        "This error is raised when queried RDF class instance " " does not return any triples that define it."
    )
    example: str = ""
    fix: str = "Make sure that RDF class instance holds necessary triples that define it."

    def __init__(self, id_: str | URIRef, verbose: bool = False):
        self.message = (
            f"Instance {id_} does not contain triples that would define it!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertyRequiredButNotProvided(NeatException):
    """This error is raised when instantiating in-memory pydantic model from graph class
    instance which is missing required property.

    Args:
        id_: instance id
        verbose: flag that indicates whether to provide enhanced exception message, by default False
    """

    type_: str = "PropertyRequiredButNotProvided"
    code: int = 405
    description: str = (
        "This error is raised when instantiating in-memory pydantic model"
        " from graph class instance which is missing required property."
    )
    example: str = ""
    fix: str = "Either make field optional or add missing property to graph instance."

    def __init__(self, property: str, id_: str | URIRef, verbose: bool = False):
        self.message = (
            f"Property {property} is not present in graph instance {id_}!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class DataModelOrItsComponentsAlreadyExist(NeatException):
    """This error is raised when attempting to create data model which already exist in DMS

    Args:
        existing_data_model: external_id of model that already exist in DMS
        existing_containers: set of external_ids of containers that already exist in DMS
        existing_views: set of external_ids of views that already exist in DMS
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Remove existing data model and underlying views and/or containers, or bump
        version of data model and views and/ir optionally delete containers.
    """

    type_: str = "DataModelOrItsComponentsAlreadyExist"
    code: int = 406
    description: str = "This error is raised when attempting to create data model which already exist in DMS."
    example: str = ""
    fix: str = (
        "Remove existing data model and underlying views and/or containers, or bump "
        "version of data model and views and optionally delete containers."
    )

    def __init__(
        self,
        existing_spaces: set[str] | None,
        existing_data_model: DataModelId | None,
        existing_containers: set[str],
        existing_views: set[str],
        verbose: bool = False,
    ):
        self.existing_spaces = existing_spaces
        self.existing_data_model = existing_data_model
        self.existing_containers = existing_containers
        self.existing_views = existing_views

        self.message = "Aborting data model creation!"
        if self.existing_spaces:
            self.message += (
                f"\nSpaces {self.existing_spaces} already exists in DMS! Delete them or skip their creation! "
            )
        if self.existing_data_model:
            self.message += (
                f"\nData model {self.existing_data_model} already exists in DMS! Delete it first or bump its version! "
            )
        if self.existing_views:
            self.message += (
                f"\nViews {self.existing_views} already exist in DMS! Delete them first or bump their versions! "
            )
        if self.existing_containers:
            self.message += f"\nContainers {self.existing_containers} already exist in DMS! Delete them first! "

        self.message += (
            "\nTo remove existing data model and its components, use `self.remove_data_model(client)` method."
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class InstancePropertiesNotMatchingViewProperties(NeatException):
    """This error is raised when an instance of a class has properties which are not
    defined in the DMS container

    Args:
        class_name: class name of instance that raised exception
        class_properties: list of mandatory properties of class
        container_properties: list of properties of container
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Make sure that all properties of a class are defined in the DMS container.
    """

    type_: str = "InstancePropertiesNotMatchingViewProperties"
    code: int = 407
    description: str = "Instance of a class has properties which are not defined in the DMS view"
    example: str = ""
    fix: str = "Make sure that all properties of a class are defined in the DMS view"

    def __init__(self, class_name: str, class_properties: list[str], view_properties: list[str], verbose: bool = False):
        self.message = (
            f"Instance of class {class_name} has properties {class_properties}"
            f" while DMS view  {class_name} has properties {view_properties}!"
            f" Cannot create instance in DMS as properties do not match!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ContainerPropertyValueTypeRedefinition(NeatException):
    """This error is raised when building up container where a property being redefined
    with different value type

    Args:
        container_id: container id that raised exception
        property_id: container property id that raised exception
        value_type: value type of container property that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Make sure that when redefining property in container, value type is the same
    """

    type_: str = "ContainerPropertyValueTypeRedefinition"
    code: int = 408
    description: str = "Container property value type is being redefined"
    example: str = ""
    fix: str = "Make sure that when redefining property in container, value type remains the same"

    def __init__(
        self,
        container_id: str,
        property_id: str,
        current_value_type: str,
        redefined_value_type: str,
        loc: str,
        verbose: bool = False,
    ):
        self.message = (
            f"Container {container_id} property {property_id}"
            f" value type {current_value_type} redefined to {redefined_value_type}!"
            f"{loc}"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ViewPropertyRedefinition(NeatException):
    """This error is raised when building up views where a property being redefined differently

    Args:
        view_id: view id that raised exception
        property_id: view property id that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Avoid redefining property in the same view
    """

    type_: str = "ViewPropertyRedefinition"
    code: int = 409
    description: str = "View property is being redefined in the same view but differently"
    example: str = ""
    fix: str = "Avoid redefining property in the same view"

    def __init__(
        self,
        view_id: str,
        property_id: str,
        loc: str,
        verbose: bool = False,
    ):
        self.message = (
            f"View {view_id} property {property_id} has been redefined in the same view!"
            f"{loc}"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


# Warnings
class OntologyMultiTypeProperty(NeatWarning):
    """This warning occurs when a same property is define for two object/classes where
    its expected value type is different in one definition, e.g. acts as an edge, while in
    other definition acts as and attribute

    Args:
        property_id: property id that raised warning due to multi type definition
        types: list of types of property
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        If a property takes different value types for different objects, simply define
        new property. It is bad practice to have multi type property!
    """

    type_: str = "OntologyMultiTypeProperty"
    code: int = 400
    description: str = (
        "This warning occurs when a same property is define for two object/classes where"
        " its expected value type is different in one definition, e.g. acts as an edge, while in "
        "other definition acts as and attribute"
    )
    example: str = ""
    fix: str = "If a property takes different value types for different objects, simply define new property"

    def __init__(self, property_id: str = "", types: list[str] | None = None, verbose: bool = False):
        self.message = (
            "It is bad practice to have multi type property! "
            f"Currently property '{property_id}' is defined as multi type property: {', '.join(types or [])}"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class OntologyMultiRangeProperty(NeatWarning):
    """This warning occurs when a property takes range of values which consists of union
    of multiple value types

    Args:
        property_id: property id that raised warning due to multi range definition
        range_of_values: list of ranges that property takes
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        If a property takes different range of values, simply define new property.
    """

    type_: str = "OntologyMultiRangeProperty"
    code: int = 401
    description: str = (
        "This warning occurs when a property takes range of values which consists of union of multiple value types."
    )
    example: str = ""
    fix: str = "If a property takes different range of values, simply define new property"

    def __init__(self, property_id: str = "", range_of_values: list[str] | None = None, verbose: bool = False):
        self.message = (
            "It is bad practice to have property that take various range of values! "
            f"Currently property '{property_id}' has multiple ranges: {', '.join(range_of_values or [])}"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class OntologyMultiDomainProperty(NeatWarning):
    """This warning occurs when a property is reused for more than one classes

    Args:
        property_id: property id that raised warning due to reuse definition
        classes: list of classes that use the same property
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        No need to fix this, but make sure that property type is consistent across different
        classes and that ideally takes the same range of values
    """

    type_: str = "OntologyMultiDomainProperty"
    code: int = 402
    description: str = "This warning occurs when a property is reused for more than one classes."
    example: str = ""
    fix: str = (
        "No need to fix this, but make sure that property type is consistent"
        " across different classes and that ideally takes the same range of values"
    )

    def __init__(self, property_id: str = "", classes: list[str] | None = None, verbose: bool = False):
        self.message = (
            f"Currently property '{property_id}' is defined for multiple classes: {', '.join(classes or [])}"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class OntologyMultiLabeledProperty(NeatWarning):
    """This warning occurs when a property is given multiple labels, typically if the
    same property is defined for different classes but different name is given

    Args:
        property_id: property id that raised warning due to multiple labels
        names: list of names of property
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        This would be automatically fixed by taking the first label (aka name) of the property.
    """

    type_: str = "OntologyMultiLabeledProperty"
    code: int = 403
    description: str = (
        "This warning occurs when a property is given multiple labels,"
        " typically if the same property is defined for different "
        "classes but different name is given."
    )
    example: str = ""
    fix: str = "This would be automatically fixed by taking the first label (aka name) of the property."

    def __init__(self, property_id: str = "", names: list[str] | None = None, verbose: bool = False):
        self.message = (
            "Property should have single preferred label (human readable name)."
            f"Currently property '{property_id}' has multiple preferred labels: {', '.join(names or [])} !"
            f"Only the first name, i.e. '{names[0] if names else ''}' will be considered!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class OntologyMultiDefinitionProperty(NeatWarning):
    """This warning occurs when a property is given multiple human readable definitions,
    typically if the same property is defined for different classes where each definition
    is different.

    Args:
        property_id: property id that raised warning due to multiple definitions
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        This would be automatically fixed by concatenating all definitions.
    """

    type_: str = "OntologyMultiDefinitionProperty"
    code: int = 404
    description: str = (
        "This warning occurs when a property is given multiple human readable definitions,"
        " typically if the same property is defined for different "
        "classes where each definition is different."
    )
    example: str = ""
    fix: str = "This would be automatically fixed by concatenating all definitions."

    def __init__(self, property_id: str, verbose: bool = False):
        self.message = (
            f"Multiple definitions (aka comments) of property '{property_id}' detected."
            " Definitions will be concatenated."
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class FieldNotFoundInInstance(NeatWarning):
    """This warning occurs when a property, associated to the pydantic field, is not found in the instance.
    The missing field will be removed, which might lead to failure of the pydantic model validation if
    the field/property is mandatory.

    Args:
        id_: instance id that raised warning due to missing field
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        If property/field is mandatory make sure that instances contain all mandatory fields.
        Otherwise, no need to fix this warning.
    """

    type_: str = "FieldNotFoundInInstance"
    code: int = 405
    description: str = (
        "This warning occurs when a property, associated to the pydantic field, is not found in the instance."
        "The missing field will be removed, which might lead to failure of the pydantic model validation if"
        " the field/property is mandatory."
    )
    example: str = ""
    fix: str = (
        "If property/field is mandatory make sure that instances contain all mandatory fields."
        "Otherwise, no need to fix this warning."
    )

    def __init__(self, id_: str | URIRef = "", field_name: str = "", verbose: bool = False):
        self.message = (
            f"Field {field_name} is missing in the instance {id_}."
            " If this field is mandatory, the validation of the pydantic model will fail!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class FieldContainsMoreThanOneValue(NeatWarning):
    """This warning occurs when a property, associated to the pydantic field, contains
    more than one value (i.e. list of values), while it is defined as single value field.
    As consequence, only the first value will be considered!

    Args:
        field_name: field name that raised warning due to multiple values
        no_of_values: number of values that field contains
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        If a property takes more than one value, define it as list of values in TransformationRules.
        To do this do not bound its `max_count` to 1, either leave it blank or set it to >1.
    """

    type_: str = "FieldContainsMoreThanOneValue"
    code: int = 406
    description: str = (
        "This warning occurs when a property, associated to the pydantic field, contains"
        " more than one value (i.e. list of values), while it is defined as single value field."
        " As consequence, only the first value will be considered!"
    )
    example: str = ""
    fix: str = (
        "If a property takes more than one value, define it as list of values in TransformationRules."
        "To do this do not bound its `max_count` to 1, either leave it blank or set it to >1."
    )

    def __init__(self, field_name: str = "", no_of_values: int | None = None, verbose: bool = False):
        self.message = (
            f"Field {field_name} is defined as single value property in TransformationRules,"
            f" but it contains {no_of_values} values!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class ContainerPropertyTypeUnsupported(NeatWarning):
    """This warning occurs when a property type is not supported by the container.
    Currently only `DatatypeProperty` and `ObjectProperty` are supported, which
    translate to `attribute` and `edge` respectively.

    Args:
        property_id: property id that raised warning due to unsupported type
        unsupported_type: unsupported property type
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Contact the NEAT support team if the warning is raised.
    """

    type_: str = "ContainerPropertyTypeUnsupported"
    code: int = 407
    description: str = (
        "This warning occurs when a property type is not supported by the container."
        " Currently only `DatatypeProperty` and `ObjectProperty` are supported, which"
        " translate to `attribute` and `edge` respectively."
    )
    example: str = ""
    fix: str = "Contact NEAT support team."

    def __init__(self, property_id: str = "", unsupported_type: str = "", verbose: bool = False):
        self.message = (
            f"Property {property_id} has unsupported type {unsupported_type}!"
            "Only DatatypeProperty and ObjectProperty are supported!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class ViewPropertyTypeUnsupported(NeatWarning):
    """This warning occurs when a TransformationRule property translates to unsupported
    DMS view property. Currently only attributes, edges 1-1 and edges 1-n are supported.

    Args:
        property_id: property id that raised warning due to unsupported type
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Contact the NEAT support team if the warning is raised.
    """

    type_: str = "ViewPropertyTypeUnsupported"
    code: int = 408
    description: str = (
        "This warning occurs when a TransformationRule property translates to unsupported DMS view property."
        " Currently only attributes, edges 1-1 and edges 1-n are supported."
    )
    example: str = ""
    fix: str = "Contact NEAT support team."

    def __init__(self, property_id: str = "", verbose: bool = False):
        self.message = (
            f"Property {property_id} translates to unsupported!"
            " Currently only attributes, edges 1-1 and edges 1-n are supported."
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class ContainersAlreadyExist(NeatWarning):
    """This warning occurs when attempting to create containers which already exist in DMS.

    Args:
        container_ids: set of container ids that already exist in DMS
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        If you need to create containers remove existing once and try again.
    """

    type_: str = "ContainersAlreadyExist"
    code: int = 409
    description: str = "This warning occurs when attempting to create containers which already exist in DMS."
    example: str = ""
    fix: str = "Remove existing containers and try again."

    def __init__(self, container_ids: set[ContainerId] | None = None, space: str = "", verbose: bool = False):
        self.message = (
            f"Containers {container_ids or set()} already exist in space {space}. "
            "Since update of containers can cause issues, "
            "remove them first prior data model creation!"
            "Aborting containers creation!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class ViewsAlreadyExist(NeatWarning):
    """This warning occurs when attempting to create views which already exist in DMS.

    Args:
        views_ids: set of view ids that already exist in DMS
        version: version of data model/views that already exist in DMS
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        If you need to create views remove existing once and try again or update
        data model version.
    """

    type_: str = "ViewsAlreadyExist"
    code: int = 410
    description: str = "This warning occurs when attempting to create views which already exist in DMS."
    example: str = ""
    fix: str = "Remove existing views and try again or update version of data model."

    def __init__(self, views_ids: set[ViewId] | None = None, version: str = "", space: str = "", verbose: bool = False):
        self.message = (
            f"Views {views_ids or set()} version {version} already exist in space {space}. "
            "Since update of views raise issues, "
            "remove them first prior data model creation or update version of data model!"
            "Aborting views creation!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class DataModelAlreadyExist(NeatWarning):
    """This warning occurs when attempting to create data model which already exist in DMS.

    Args:
        data_model_id: data model id that already exist in DMS
        version: version of data model that already exist in DMS
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Remove existing data model and try again or update its version
    """

    type_: str = "DataModelAlreadyExist"
    code: int = 411
    description: str = "This warning occurs when attempting to create data model which already exist in DMS."
    example: str = ""
    fix: str = "Remove existing data model and try again or update its version."

    def __init__(self, data_model_id: str = "", version: str = "", space: str = "", verbose: bool = False):
        self.message = (
            f"Data model {data_model_id} version {version} already exist in space {space}. "
            "Since update of data model can raise issues, "
            "remove it first or update its version!"
            "Aborting data model creation!"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class EdgeConditionUnmet(NeatWarning):
    """This warning occurs when attempting to create an edge but not all conditions are met.

    Args:
        edge: data model id that already exist in DMS
        verbose: flag that indicates whether to provide enhanced exception message, by default False
    """

    type_: str = "EdgeConditionUnmet"
    code: int = 412
    description: str = "This warning occurs when attempting to create an edge, but the conditions are not met."
    example: str = ""
    fix: str = "Check if the edge is valid and that the lenght of the external_id is < 255"

    def __init__(self, edge: str, verbose: bool = False):
        self.message = (
            f"Ignoring edge {edge} as its format is not valid"
            f"\nFor more information visit: {DOCS_BASE_URL}.{self.__class__.__name__}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
