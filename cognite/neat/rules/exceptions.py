"""This module contains the definition of validation errors and warnings raised when parsing transformation rules.
CODES:
- 0 - 99: reserved for errors and warnings related to general errors/warnings
- 100 - 199: reserved for Metadata sheet
- 200 - 299: reserved for Classes sheet
- 300 - 399: reserved for Properties sheet
- 400 - 499: reserved for Prefixes sheet
- 500 - 599: reserved for Instances sheet
- 600 - 699: reserved for Transformation Rules, usually checking inter-sheet dependencies
"""

#########################################
# Metadata sheet Error Codes 100 - 199: #
from typing import Any

from rdflib import URIRef

from cognite.neat.exceptions import NeatException, NeatWarning


class ExcelFileMissingMandatorySheets(NeatException):
    type_: str = "ExcelFileMissingMandatorySheets"
    code: int = 0
    description: str = "Given Excel file is missing mandatory sheets"
    example: str = ""
    fix: str = ""

    def __init__(self, missing_sheets: set[str], verbose=False):
        self.missing_fields = missing_sheets

        self.message = (
            "Given Excel file is not compliant Transformation Rules file."
            f" It is missing mandatory sheets: {', '.join(missing_sheets)}"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class NotValidRDFPath(NeatException):
    type_: str = "NotValidRDFPath"
    code: int = 1
    description: str = "Provided rdf path is not valid, i.e. it cannot be converted to SPARQL query"
    example: str = ""
    fix: str = "Get familiar with RDF paths and check if provided path is valid"

    def __init__(self, rdf_path, verbose=False):
        self.rdf_path = rdf_path

        self.message = f"{self.rdf_path} is not a valid rdfpath!"

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class NotValidTableLookUp(NeatException):
    type_: str = "NotValidTableLookUp"
    code: int = 2
    description: str = "Provided table lookup is not valid, i.e. it cannot be converted to CDF lookup"
    example: str = ""
    fix: str = "Get familiar with RAW look up and RDF paths and check if provided rawlookup is valid"

    def __init__(self, table_look_up, verbose=False):
        self.table_look_up = table_look_up

        self.message = f"{self.table_look_up} is not a valid table lookup"

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class NotValidRAWLookUp(NeatException):
    type_: str = "NotValidRAWLookUp"
    code: int = 3
    description: str = "Provided rawlookup is not valid, i.e. it cannot be converted to SPARQL query and CDF lookup"
    example: str = ""
    fix: str = "Get familiar with RAW look up and RDF paths and check if provided rawlookup is valid"

    def __init__(self, raw_look_up, verbose=False):
        self.raw_look_up = raw_look_up

        self.message = f"Invalid rawlookup expected traversal | table lookup, got {raw_look_up}"

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class EntitiesContainNonDMSCompliantCharacters(NeatException):
    type_: str = "EntitiesContainNonDMSCompliantCharacters"
    code: int = 10
    description: str = (
        "This error is raised during export of Transformation Rules to"
        " DMS schema when entities contain non DMS compliant characters."
    )
    example: str = ""
    fix: str = "Make sure to check validation report of Transformation Rules and fix DMS related warnings."

    def __init__(self, report: str = "", verbose=False):
        self.message = f"Following entities contain non DMS compliant characters: {report}"

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertiesDefinedMultipleTimes(NeatException):
    type_: str = "PropertiesDefinedMultipleTimes"
    code: int = 11
    description: str = (
        "This error is raised during export of Transformation Rules to "
        "DMS schema when properties are defined multiple times for the same class."
    )
    example: str = ""
    fix: str = "Make sure to check validation report of Transformation Rules and fix DMS related warnings."

    def __init__(self, report: str = "", verbose=False):
        self.message = f"Following properties defined multiple times for the same class(es): {report}"

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class UnableToDownloadExcelFile(NeatException):
    type_: str = "UnableToDownloadExcelFile"
    code: int = 11
    description: str = (
        "This error is raised during loading of byte representation of"
        " a Excel file from Github when given file cannot be downloaded."
    )
    example: str = ""
    fix: str = "Make sure you provided correct parameters to download Excel file from github repository"

    def __init__(self, filepath: str, loc: str, reason: str, verbose=False):
        self.message = f"File '{filepath}' from '{loc}' cannot be downloaded! Reason: {reason}"

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class NotExcelFile(NeatException):
    type_: str = "NotExcelFile"
    code: int = 11
    description: str = (
        "This error is raised during loading of byte representation of a file from Github"
        " into openpyxl workbook object in case when byte representation is not Excel file."
    )
    example: str = ""
    fix: str = "Make sure you that byte representation of a file is Excel file!"

    def __init__(self, filepath: str, loc: str, verbose=False):
        self.message = f"File '{filepath}' from '{loc}' is not a valid excel file!"

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertyDefinitionsNotForSameProperty(NeatException):
    type_: str = "PropertyDefinitionsNotForSameProperty"
    code: int = 30
    description: str = "This error is raised if property definitions are not for linked to the same property id"
    example: str = ""
    fix: str = ""

    def __init__(self, verbose=False):
        self.message = "All definitions should have the same property_id! Aborting."

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class FieldValueOfUnknownType(NeatException):
    type_: str = "FieldValueOfUnknownType"
    code: int = 40
    description: str = (
        "This error is raised when generating in-memory pydantic model"
        " from Transformation Rules from model, when field definitions are not"
        " provided as dictionary of field names ('str') and their types ('tuple' or 'dict')."
    )
    example: str = ""
    fix: str = ""

    def __init__(self, field: str, definition: Any, verbose=False):
        self.message = (
            f"Field {field} has definition of type {type(definition)}"
            " which is not acceptable! Only definition in form of dict or tuple is acceptable!"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class FieldRequiredButNotProvided(NeatException):
    type_: str = "FieldRequiredButNotProvided"
    code: int = 41
    description: str = (
        "This error is raised when instantiating in-memory pydantic model"
        " from graph class instance which is missing required field (i.e., property)."
    )
    example: str = ""
    fix: str = "Either make field optional or add missing property to graph instance."

    def __init__(self, field: str, id_: str | URIRef, verbose=False):
        self.message = f"Field {field} is not present in graph instance {id_}!"

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class MetadataSheetMissingMandatoryFields(NeatException):
    type_: str = "MetadataSheetMissingMandatoryFields"
    code: int = 51
    description: str = "Metadata sheet, which is part of Transformation Rules Excel file, is missing mandatory rows"
    example: str = ""
    fix: str = ""

    def __init__(self, missing_fields: set[str], verbose=False):
        self.missing_fields = missing_fields

        self.message = f"Metadata sheet is missing following mandatory fields: {', '.join(missing_fields)}"

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ClassesSheetMissingMandatoryColumns(NeatException):
    type_: str = "ClassesSheetMissingMandatoryColumns"
    code: int = 52
    description: str = (
        "Classes sheet, which is a mandatory part of Transformation Rules Excel file, "
        "is missing mandatory columns at row 2"
    )
    example: str = ""
    fix: str = ""

    def __init__(self, missing_fields: set[str], verbose=False):
        self.missing_fields = missing_fields

        self.message = f"Classes sheet is missing following mandatory columns: {', '.join(missing_fields)} at row 2"

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertiesSheetMissingMandatoryColumns(NeatException):
    type_: str = "PropertiesSheetMissingMandatoryColumns"
    code: int = 53
    description: str = (
        "Properties sheet, which is a mandatory part of Transformation Rules Excel file, "
        "is missing mandatory columns at row 2"
    )
    example: str = ""
    fix: str = ""

    def __init__(self, missing_fields: set[str], verbose=False):
        self.missing_fields = missing_fields

        self.message = f"Properties sheet is missing following mandatory columns: {', '.join(missing_fields)} at row 2"

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PrefixesSheetMissingMandatoryColumns(NeatException):
    type_: str = "PrefixesSheetMissingMandatoryColumns"
    code: int = 54
    description: str = (
        "Prefixes sheet, which is part of Transformation Rules Excel file, is missing mandatory columns at row 1"
    )
    example: str = ""
    fix: str = ""

    def __init__(self, missing_fields: set[str], verbose=False):
        self.missing_fields = missing_fields

        self.message = f"Prefixes sheet is missing following mandatory columns: {', '.join(missing_fields)} at row 1"

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class InstancesSheetMissingMandatoryColumns(NeatException):
    type_: str = "InstancesSheetMissingMandatoryColumns"
    code: int = 55
    description: str = (
        "Instances sheet, which is part of Transformation Rules Excel file, is missing mandatory columns at row 1"
    )
    example: str = ""
    fix: str = ""

    def __init__(self, missing_fields: set[str], verbose=False):
        self.missing_fields = missing_fields

        self.message = f"Instances sheet is missing following mandatory columns: {', '.join(missing_fields)} at row 1"

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


# Metadata sheet Error and Warning Codes 100 - 199:
class PrefixRegexViolation(NeatException):
    type_: str = "PrefixRegexViolation"
    code: int = 100
    description: str = "Prefix, which is in the 'Metadata' sheet, does not respect defined regex expression"
    example: str = (
        "If prefix is set to 'power grid', while regex expression does not "
        "allow spaces, the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check if prefix in the 'Metadata' sheet contains any illegal characters and respects the regex expression"
    )

    def __init__(self, prefix, regex_expression, verbose=False):
        self.prefix = prefix
        self.regex_expression = regex_expression

        self.message = (
            f"Invalid prefix '{self.prefix}' stored in 'Metadata' sheet, it must obey regex {self.regex_expression}!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class CDFSpaceRegexViolation(NeatException):
    type_: str = "CDFSpaceRegexViolation"
    code: int = 101
    description: str = "cdfSpaceName, which is in the 'Metadata' sheet, does not respect defined regex expression"
    example: str = (
        "If cdfSpaceName is set to 'power grid', while regex expression does not "
        "allow spaces, the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check if cdfSpaceName in the 'Metadata' sheet "
        "contains any illegal characters and respects the regex expression"
    )

    def __init__(self, cdf_space_name, regex_expression, verbose=False):
        self.cdf_space_name = cdf_space_name
        self.regex_expression = regex_expression

        self.message = (
            f"Invalid cdfSpaceName '{self.cdf_space_name}' stored in 'Metadata' sheet, "
            f"it must obey regex {self.regex_expression}!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class MetadataSheetNamespaceNotValidURL(NeatException):
    type_: str = "MetadataSheetNamespaceNotValidURL"
    code: int = 102
    description: str = "namespace, which is in the 'Metadata' sheet, is not valid URL"
    example: str = "If we have 'authority:namespace' as namespace as it is not a valid URL this error will be raised"
    fix: str = (
        "Check if 'namespace' in the 'Metadata' sheet is properly "
        "constructed as valid URL containing only allowed characters"
    )

    def __init__(self, namespace, verbose=False):
        self.namespace = namespace

        self.message = f"Invalid namespace '{self.namespace}' stored in 'Metadata' sheet, it must be valid URL!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class DataModelNameRegexViolation(NeatException):
    type_: str = "DataModelNameRegexViolation"
    code: int = 103
    description: str = "dataModelName, which is in the 'Metadata' sheet, does not respect defined regex expression"
    example: str = (
        "If dataModelName is set to 'power grid data model', while regex expression does not "
        "allow spaces, the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check if dataModelName in the 'Metadata' sheet contains any illegal "
        "characters and respects the regex expression"
    )

    def __init__(self, data_model_name, regex_expression, verbose=False):
        self.data_model_name = data_model_name
        self.regex_expression = regex_expression

        self.message = (
            f"Invalid dataModelName '{self.data_model_name}' stored in 'Metadata' sheet, "
            f"it must obey regex {self.regex_expression}!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class VersionRegexViolation(NeatException):
    type_: str = "VersionRegexViolation"
    code: int = 104
    description: str = "version, which is in the 'Metadata' sheet, does not respect defined regex expression"
    example: str = (
        "If version is set to '1.2.3 alpha4443', while regex expression does not "
        "allow spaces, the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check if version in the 'Metadata' sheet contains any illegal characters and respects the regex expression"
    )

    def __init__(self, version, regex_expression, verbose=False):
        self.version = version
        self.regex_expression = regex_expression

        self.message = (
            f"Invalid version '{self.version}' stored in 'Metadata' sheet, it must obey regex {self.regex_expression}!"
            f"\n\tFor further information visit https://thisisneat.io/errors/Error{self.code}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class DataModelOrItsComponentsAlreadyExist(NeatException):
    type_: str = "DataModelOrItsComponentsAlreadyExist"
    code: int = 60
    description: str = "This error is raised when attempting to create data model which already exist in DMS."
    example: str = ""
    fix: str = (
        "Remove existing data model and underlying views and/or containers, or bump "
        "version of data model and views and optionally delete containers."
    )

    def __init__(self, existing_data_model, existing_containers, existing_views, verbose=False):
        self.existing_data_model = existing_data_model
        self.existing_containers = existing_containers
        self.existing_views = existing_views

        self.message = "Aborting data model creation!"
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
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class InstancePropertiesNotMatchingContainerProperties(NeatException):
    type_: str = "InstancePropertiesNotMatchingContainerProperties"
    code: int = 61
    description: str = "Instance of a class has properties which are not defined in the DMS container"
    example: str = ""
    fix: str = "Make sure that all properties of a class are defined in the DMS container"

    def __init__(self, class_name, class_properties, container_properties, verbose=False):
        self.existing_data_model = existing_data_model
        self.existing_containers = existing_containers
        self.existing_views = existing_views

        self.message = (f"Instance of class {class_name} has properties {class_properties}"
                        f" while DMS container  {class_name} has properties {container_properties}!"
                        f" Cannot create instance in DMS as properties do not match!")

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


########################################
# Classes sheet Error Codes 200 - 199: #


class ClassSheetClassIDRegexViolation(NeatException):
    type_: str = "ClassSheetClassIDRegexViolation"
    code: int = 200
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

    def __init__(self, class_id, regex_expression, verbose=False):
        self.class_id = class_id
        self.regex_expression = regex_expression

        self.message = (
            f"Class id '{self.class_id}' stored in 'Class' column in 'Classes' "
            f"sheet violates regex {self.regex_expression}!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ClassIDMissing(NeatException):
    type_: str = "ClassIDMissing"
    code: int = 200
    description: str = (
        "Class ID, which is stored in the column 'Class' in the 'Classes' sheet,"
        " is either missing or did not satisfied regex expression"
    )
    example: str = ""
    fix: str = "Make sure that class id is provided and respects regex expression"

    def __init__(self, verbose=False):
        self.message = (
            "Class id is missing, it failed validation either because it has"
            " not been provided or because it did not respect regex expression!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ClassNameNotProvided(NeatWarning):
    type_: str = "ClassNameNotProvided"
    code: int = 200
    description: str = (
        "If class name is not provided in the 'Classes' sheet under 'name' column,"
        " it will be set to corresponding value from 'Class' column, thus class id"
    )
    example: str = ""
    fix: str = "If you want to have different class name than class id, provide it in the 'name' column"

    def __init__(self, class_id, verbose=False):
        self.message = f"Class id {class_id} set as Class name!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page


###########################################
# Properties sheet Error Codes 300 - 399: #


class PropertiesSheetClassIDRegexViolation(NeatException):
    type_: str = "PropertiesSheetClassIDRegexViolation"
    code: int = 300
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

    def __init__(self, class_id, regex_expression, verbose=False):
        self.class_id = class_id
        self.regex_expression = regex_expression

        self.message = (
            f"Class id '{self.class_id}' stored in 'Class' column in 'Properties' "
            f"sheet violates regex {self.regex_expression}!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertyIDRegexViolation(NeatException):
    type_: str = "PropertyIDRegexViolation"
    code: int = 301
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

    def __init__(self, property_id, regex_expression, verbose=False):
        self.property_id = property_id
        self.regex_expression = regex_expression

        self.message = (
            f"Property id '{self.property_id}' stored in 'Property' "
            f"column in 'Properties' sheet violates regex {self.regex_expression}!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ValueTypeIDRegexViolation(NeatException):
    type_: str = "ValueTypeIDRegexViolation"
    code: int = 302
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

    def __init__(self, value_type, regex_expression, verbose=False):
        self.value_type = value_type
        self.regex_expression = regex_expression

        self.message = (
            f"Value type '{self.value_type}' stored in 'Type' column in "
            f"'Properties' sheet violates regex {self.regex_expression}!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class MissingTypeValue(NeatException):
    type_: str = "MissingTypeValue"
    code: int = 302
    description: str = "Value type, which is stored in the column 'Type' in the 'Properties' sheet, is missing"
    example: str = "If value type is not set, this error will be raised"
    fix: str = "Make sure to define value type in 'Type' column in 'Properties' sheet"

    def __init__(self, verbose=False):
        self.message = "Value type, which is stored in the column 'Type' in the 'Properties' sheet, is missing"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertyIDMissing(NeatException):
    type_: str = "PropertyIDMissing"
    code: int = 304
    description: str = (
        "Property ID, which is stored in the column 'Property' in the 'Properties' sheet,"
        " is either missing or did not satisfied regex expression"
    )
    example: str = ""
    fix: str = "Make sure that property id is provided and respects regex expression"

    def __init__(self, verbose=False):
        self.message = (
            "Property id is missing, validator for property id failed either"
            " due to lack of property id or due to not respecting regex expression!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class RuleTypeProvidedButRuleMissing(NeatException):
    type_: str = "RuleTypeProvidedButRuleMissing"
    code: int = 305
    description: str = (
        "This error occurs when transformation rule type is provided but actual transformation rule is missing"
    )
    example: str = ""
    fix: str = (
        "If you provide rule type you are must provide rule as well! "
        "Otherwise remove rule type if no transformation rule is needed"
    )

    def __init__(self, property_id, class_id, rule_type, verbose=False):
        self.message = (
            f"Rule type '{rule_type}' provided for property '{property_id}' "
            f"in class '{class_id}' but rule is not provided!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PropertyNameNotProvided(NeatWarning):
    type_: str = "PropertyNameNotProvided"
    code: int = 300
    description: str = (
        "If property name is not provided in the 'Property' sheet under 'name' column,"
        " it will be set to corresponding value from 'Property' column, thus property id"
    )
    example: str = ""
    fix: str = "If you want to have different property name than property id, provide it in the 'name' column"

    def __init__(self, property_id, verbose=False):
        self.message = f"Property id {property_id} set as Property name!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class MissingLabel(NeatWarning):
    type_: str = "MissingLabel"
    code: int = 301
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

    def __init__(self, property_id, verbose=False):
        self.message = f"Property id {property_id} set as CDF relationship label!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class NoTransformationRules(NeatWarning):
    type_: str = "NoTransformationRules"
    code: int = 302
    description: str = (
        "This warning is raised if there are no transformation rules "
        "defined in the 'Transformation' sheet for given propertuy"
    )
    example: str = ""
    fix: str = "No fix is provided for this warning"

    # need to have default value set otherwise
    # will raise TypeError: __init__() missing 1 required positional argument: 'property_id'
    # not happy with this solution but it works
    def __init__(self, property_id: str = "", class_id: str = "", verbose=False):
        self.message = f"There is no transformation rule configured for class '{class_id}' property '{property_id}'!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


###############################################
#  Prefixes  Error Codes 400 - 499: #


class PrefixesRegexViolation(NeatException):
    type_: str = "PrefixesRegexViolation"
    code: int = 400
    description: str = "Prefix(es), which are in the 'Prefixes' sheet, do(es) not respect defined regex expression"
    example: str = (
        "If prefix is set to 'power grid', while regex expression does not "
        "allow spaces, the expression will be violated thus raising this error"
    )
    fix: str = (
        "Check if prefixes in the 'Prefixes' sheet contains any illegal characters and respects the regex expression"
    )

    def __init__(self, prefixes, regex_expression, verbose=False):
        self.prefixes = prefixes
        self.regex_expression = regex_expression

        self.message = (
            f"Invalid prefix(es) {', '.join(self.prefixes)} stored in the 'Prefixes' sheet, "
            f"it/they must obey regex {self.regex_expression}!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class PrefixesSheetNamespaceNotValidURL(NeatException):
    type_: str = "PrefixesSheetNamespaceNotValidURL"
    code: int = 401
    description: str = "namespace(es), which are/is in the 'Prefixes' sheet, are/is not valid URLs"
    example: str = "If we have 'authority:namespace' as namespace as it is not a valid URL this error will be raised"
    fix: str = (
        "Check if 'namespaces' in the 'Prefixes' sheet are properly "
        "constructed as valid URLs containing only allowed characters"
    )

    def __init__(self, namespaces, verbose=False):
        self.namespaces = namespaces

        self.message = (
            f"Invalid namespace(es) {', '.join(self.namespaces)} stored in the 'Prefixes' sheet, "
            f"it/they must be valid URLs!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


###############################################
# Instances Error Codes 500 - 599: #


class MissingDataModelPrefixOrNamespace(NeatWarning):
    type_: str = "MissingDataModelPrefixOrNamespace"
    code: int = 500
    description: str = "Either prefix or namespace or both are missing in the 'Metadata' sheet"
    example: str = ""
    fix: str = "Add missing prefix and/or namespace in the 'Metadata' sheet"

    def __init__(self, verbose=False):
        self.message = (
            "Instances sheet is present but prefix and/or namespace are missing in 'Metadata' sheet."
            "Instances sheet will not be processed!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page


###############################################
# Transformation Rules Error Codes 600 - 699: #


class EntityIDNotDMSCompliant(NeatWarning):
    type_: str = "EntityIDNotDMSCompliant"
    code: int = 600
    description: str = "Warning raise when entity id being class, property or value type is not DMS compliant"
    example: str = ""
    fix: str = (
        "DMS ready means that entity id must only use following"
        " characters [a-zA-Z0-9_], where it can only start with letter!"
    )

    # See Warning302 for explanation why default values are set
    def __init__(self, entity_type: str = "", entity_id: str = "", loc: str = "", verbose=False):
        self.message = (
            f"'{entity_id}' {entity_type.lower()}"
            " use character(s) outside of range of allowed characters [a-zA-Z0-9_] or "
            f"it starts with non-letter character! {loc}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class PropertyRedefined(NeatWarning):
    type_: str = "PropertyRedefined"
    code: int = 600
    description: str = "Warning raise when same property is defined multiple times for same class"
    example: str = ""
    fix: str = "Have only single definition of a perticular property for a class"

    # See Warning302 for explanation why default values are set
    def __init__(self, property_id: str = "", class_id: str = "", loc: str = "", verbose=False):
        self.message = f"Not DMS compliant! Property '{property_id}' for class '{class_id}' redefined! {loc}"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page


class PropertyDefinedForUndefinedClass(NeatException):
    """Property defined for a class that has not been defined in the 'Classes' sheet"""

    type_: str = "PropertyDefinedForUndefinedClass"
    code: int = 600
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

    def __init__(self, property_id, class_id, verbose=False):
        self.property_id = property_id
        self.class_id = class_id

        self.message = (
            f"Class <{self.class_id}> to which property {self.property_id}> is being defined"
            " is not define in the 'Classes' sheet!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class MetadataSheetMissingOrFailedValidation(NeatException):
    type_: str = "MetadataSheetMissingOrFailedValidation"
    code: int = 601
    description: str = "Metadata sheet is missing or it failed validation for one or more fields"
    example: str = ""
    fix: str = "Make sure to define compliant Metadata sheet before proceeding"

    def __init__(self, verbose=False):
        self.message = "Metadata sheet is missing or it failed validation for one or more fields!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class FiledInMetadataSheetMissingOrFailedValidation(NeatException):
    type_: str = "FiledInMetadataSheetMissingOrFailedValidation"
    code: int = 602
    description: str = "One of the expected fields in Metadata sheet is missing or it failed validation"
    example: str = ""
    fix: str = "Make sure to define compliant field in Metadata sheet before proceeding"

    def __init__(self, missing_field: str, verbose=False):
        self.message = f"Field {missing_field} is missing in the 'Metadata' sheet or it failed validation!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class ValueTypeNotDefinedAsClass(NeatException):
    type_: str = "ValueTypeNotDefinedAsClass"
    code: int = 603
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

    def __init__(self, class_id: str, property_id: str, expected_value_type: str, verbose=False):
        self.message = (
            f"Property {property_id} defined for class {class_id} has"
            f" value type {expected_value_type} which is not defined as a class in the 'Classes' sheet!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class UndefinedObjectsAsExpectedValueTypes(NeatException):
    type_: str = "UndefinedObjectsAsExpectedValueTypes"
    code: int = 604
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

    def __init__(self, undefined_objects: list[str], verbose=False):
        self.message = (
            f"Following classes {', '.join(undefined_objects)} defined as classes in the 'Classes' sheet"
            f" have no properties defined in the 'Properties' sheet or their validation as objects failed!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class OWLGeneratedTransformationRulesHasErrors(NeatWarning):
    type_: str = "OWLGeneratedTransformationRulesHasErrors"
    code: int = 1
    description: str = (
        "This warning occurs when generating transformation rules from OWL ontology are invalid/incomplete."
    )
    example: str = ""
    fix: str = "Go through the generated report file and fix the warnings in generated Transformation Rules."

    def __init__(self, verbose=False):
        self.message = (
            "Transformation rules generated from OWL ontology are invalid!"
            " Consult report.txt for details on the errors and fix them before using the rules file."
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page


class OWLGeneratedTransformationRulesHasWarnings(NeatWarning):
    type_: str = "OWLGeneratedTransformationRulesHasWarnings"
    code: int = 2
    description: str = (
        "This warning occurs when generating transformation rules from OWL ontology are invalid/incomplete."
    )
    example: str = ""
    fix: str = "Go through the generated report file and fix the warnings in generated Transformation Rules."

    def __init__(self, verbose=False):
        self.message = (
            "Transformation rules generated from OWL ontology raised warnings!"
            " Consult report.txt for details on warnings, and fix them prior using the rules file."
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page


class OntologyMultiTypeProperty(NeatWarning):
    type_: str = "OntologyMultiTypeProperty"
    code: int = 30
    description: str = (
        "This warning occurs when a same property is define for two object"
        " where its expected value type is different in one case it acts as"
        " a node edge (i.e. object) in other case it acts as a node attribute"
        " (i.e. hold simple values such as strings)."
    )
    example: str = ""
    fix: str = "If a property takes different value types for different objects, simply define new property"

    def __init__(self, property_id: str = "", types: list[str] | None = None, verbose=False):
        self.message = (
            "It is bad practice to have multi type property! "
            f"Currently property '{property_id}' is defined as multi type property: {', '.join(types or [])}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class OntologyMultiRangeProperty(NeatWarning):
    type_: str = "OntologyMultiRangeProperty"
    code: int = 31
    description: str = (
        "This warning occurs when a property takes range of values" " which consists of union of multiple value types."
    )
    example: str = ""
    fix: str = "If a property takes different range of values, simply define new property for each range"

    def __init__(self, property_id: str = "", range_of_values: list[str] | None = None, verbose=False):
        self.message = (
            "Property should ideally have only single range of values. "
            f"Currently property '{property_id}' has multiple ranges: {', '.join(range_of_values or None)}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class OntologyMultiDomainProperty(NeatWarning):
    type_: str = "OntologyMultiDomainProperty"
    code: int = 32
    description: str = "This warning occurs when a property is reused/redefined for more than one classes."
    example: str = ""
    fix: str = (
        "No need to fix this, but make sure that property type is consistent"
        " across different classes and that ideally takes the same range of values"
    )

    def __init__(self, property_id: str = "", classes: list[str] | None = None, verbose=False):
        self.message = (
            "Property should ideally defined for single class. "
            f"Currently property '{property_id}' is defined for multiple classes: {', '.join(classes or [])}"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class OntologyMultiLabeledProperty(NeatWarning):
    type_: str = "OntologyMultiLabeledProperty"
    code: int = 33
    description: str = (
        "This warning occurs when a property is given multiple labels,"
        " typically if the same property is defined for different "
        "classes but different name is given."
    )
    example: str = ""
    fix: str = "This would be automatically fixes by taking the first name."

    def __init__(self, property_id: str = "", names: list[str] | None = None, verbose=False):
        self.message = (
            "Property should have single preferred label (human readable name)."
            f"Currently property '{property_id}' has multiple preferred labels: {', '.join(names or [])} !"
            f"Only the first name, i.e. '{names[0]}' will be considered!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class OntologyMultiDefinitionProperty(NeatWarning):
    type_: str = "OntologyMultiDefinitionProperty"
    code: int = 34
    description: str = (
        "This warning occurs when a property is given multiple human readable definitions,"
        " typically if the same property is defined for different "
        "classes and their usage differs from class to class."
    )
    example: str = ""
    fix: str = "This would be automatically fixes by concatenating all definitions."

    def __init__(self, property_id: str, verbose=False):
        self.message = (
            f"Multiple definitions (aka comments) of property '{property_id}' detected."
            " Definitions will be concatenated."
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class FieldNotFoundInInstance(NeatWarning):
    type_: str = "FieldNotFoundInInstance"
    code: int = 40
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

    def __init__(self, id_: str | URIRef = "", field_name: str = "", verbose=False):
        self.message = (
            f"Field {field_name} is missing in the instance {id_}."
            " If this field is mandatory, the validation of the pydantic model will fail!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class FieldContainsMoreThanOneValue(NeatWarning):
    type_: str = "FieldContainsMoreThanOneValue"
    code: int = 41
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

    def __init__(self, field_name: str = "", no_of_values: int | None = None, verbose=False):
        self.message = (
            f"Field {field_name} is defined as single value property in TransformationRules,"
            f" but it contains {no_of_values} values!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class ContainerPropertyTypeUnsupported(NeatWarning):
    type_: str = "ContainerPropertyTypeUnsupported"
    code: int = 60
    description: str = (
        "This warning occurs when a property type is not supported by the container."
        " Currently only `DatatypeProperty` and `ObjectProperty` are supported, which"
        " translate to `attribute` and `edge` respectively."
    )
    example: str = ""
    fix: str = "Contact NEAT support team."

    def __init__(self, property_id: str = "", property_type: str = "", verbose=False):
        self.message = (
            f"Property {property_id} has unsupported type {property_type}!"
            "Only DatatypeProperty and ObjectProperty are supported!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class ViewPropertyTypeUnsupported(NeatWarning):
    type_: str = "ViewPropertyTypeUnsupported"
    code: int = 61
    description: str = (
        "This warning occurs when a TransformationRule property translates to unsupported DMS view property."
        " Currently only attributes, edges 1-1 and edges 1-n are supported."
    )
    example: str = ""
    fix: str = "Contact NEAT support team."

    def __init__(self, property_id: str = "", verbose=False):
        self.message = (
            f"Property {property_id} translates to unsupported!"
            " Currently only attributes, edges 1-1 and edges 1-n are supported."
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class ContainersAlreadyExist(NeatWarning):
    type_: str = "ContainersAlreadyExist"
    code: int = 62
    description: str = "This warning occurs when attempting to create containers which already exist in DMS."
    example: str = ""
    fix: str = "Remove existing containers and try again."

    def __init__(self, container_ids: set[str] | None = None, space: str = "", verbose=False):
        self.message = (
            f"Containers {container_ids or set()} already exist in space {space}. "
            "Since update of containers can cause issues, "
            "remove them first prior data model creation!"
            "Aborting containers creation!"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class ViewsAlreadyExist(NeatWarning):
    type_: str = "ViewsAlreadyExist"
    code: int = 63
    description: str = "This warning occurs when attempting to create views which already exist in DMS."
    example: str = ""
    fix: str = "Remove existing views and try again or update version of data model."

    def __init__(self, views_ids: set[str] | None = None, version: str = "", space: str = "", verbose=False):
        self.message = (
            f"Views {views_ids or set()} version {version} already exist in space {space}. "
            "Since update of views raise issues, "
            "remove them first prior data model creation or update version of data model!"
            "Aborting views creation!"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class DataModelAlreadyExist(NeatWarning):
    type_: str = "DataModelAlreadyExist"
    code: int = 64
    description: str = "This warning occurs when attempting to create data model which already exist in DMS."
    example: str = ""
    fix: str = "Remove existing data model and try again or update its version."

    def __init__(self, data_model_id: str = "", version: str = "", space: str = "", verbose=False):
        self.message = (
            f"Data model {data_model_id} version {version} already exist in space {space}. "
            "Since update of data model can raise issues, "
            "remove it first or update its version!"
            "Aborting data model creation!"
        )

        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"


class NamespaceEndingFixed(NeatWarning):
    type_: str = "NamespaceEndingFixed"
    code: int = 100
    description: str = "It is expected that namespace ends with '/' or '#'. If not, it will be fixed"
    example: str = "If namespace is set to http://purl.org/cognite, it will be converted to http://purl.org/cognite#"
    fix: str = "Make sure that namespace ends with '/' or '#'"

    def __init__(self, namespace, verbose=False):
        self.message = f"Namespace {namespace} ending fixed by adding '#' at its end!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page


class DataModelNameMissing(NeatWarning):
    type_: str = "DataModelNameMissing"
    code: int = 101
    description: str = "In case when data model name is not provided in the 'Metadata' sheet, it will be set to prefix"
    example: str = ""
    fix: str = "Provide data model name to avoid this warning and defaulting to prefix"

    def __init__(self, prefix, verbose=False):
        self.message = f"Data model name not provided, defaulting to prefix {prefix}!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page


class VersionDotsConvertedToUnderscores(NeatWarning):
    type_: str = "VersionDotsConvertedToUnderscores"
    code: int = 102
    description: str = (
        "Version is expressed in classical form with dots major.minor.patch, "
        "while CDF accepts underscores major_minor_patch"
    )
    example: str = "If version is provided as 1.2.3, this will be converted to 1_2_3 to be accepted by CDF"
    fix: str = "Convert version to underscore notation major_minor_patch"

    def __init__(self, verbose=False):
        self.message = (
            "Data model version expressed with '.' which is illegal character for CDF. All '.' are converted to '_'!"
        )
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
            # hint on a specific web docs page
