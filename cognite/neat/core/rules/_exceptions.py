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


from pydantic_core import PydanticCustomError


class Error(Exception):
    name: str
    code: int
    description: str
    example: str
    fix: str
    message: str

    def to_pydantic_custom_error(self):
        return PydanticCustomError(
            self.name,
            self.message,
            dict(name=self.name, code=self.code, description=self.description, example=self.example, fix=self.fix),
        )


class Error1(Error):
    name: str = "NotValidRDFPath"
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


class Error2(Error):
    name: str = "NotValidTableLookUp"
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


class Error3(Error):
    name: str = "NotValidRAWLookUp"
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


# Metadata sheet Error and Warning Codes 100 - 199:
class Error100(Error):
    name: str = "PrefixRegexViolation"
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


class Error101(Error):
    name: str = "CDFSpaceRegexViolation"
    code: int = 101
    description: str = "cdfSpaceName, which is in the 'Metadata' sheet, does not respect defined regex expression"
    example: str = (
        "If cdfSpaceName is set to 'power grid', while regex expression does not "
        "allow spaces, the expression will be violated thus raising this error"
    )
    fix: str = "Check if cdfSpaceName in the 'Metadata' sheet contains any illegal characters and respects the regex expression"

    def __init__(self, cdf_space_name, regex_expression, verbose=False):
        self.cdf_space_name = cdf_space_name
        self.regex_expression = regex_expression

        self.message = f"Invalid cdfSpaceName '{self.cdf_space_name}' stored in 'Metadata' sheet, it must obey regex {self.regex_expression}!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class Error102(Error):
    name: str = "NamespaceNotValidURL"
    code: int = 102
    description: str = "namespace, which is in the 'Metadata' sheet, is not valid URL"
    example: str = "If we have 'authority:namespace' as namespace as it is not a valid URL this error will be raised"
    fix: str = "Check if 'namespace' in the 'Metadata' sheet is properly constructed as valid URL containing only allowed characters"

    def __init__(self, namespace, verbose=False):
        self.namespace = namespace

        self.message = f"Invalid namespace '{self.namespace}' stored in 'Metadata' sheet, it must be valid URL!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class Error103(Error):
    name: str = "DataModelNameRegexViolation"
    code: int = 103
    description: str = "dataModelName, which is in the 'Metadata' sheet, does not respect defined regex expression"
    example: str = (
        "If dataModelName is set to 'power grid data model', while regex expression does not "
        "allow spaces, the expression will be violated thus raising this error"
    )
    fix: str = "Check if dataModelName in the 'Metadata' sheet contains any illegal characters and respects the regex expression"

    def __init__(self, data_model_name, regex_expression, verbose=False):
        self.data_model_name = data_model_name
        self.regex_expression = regex_expression

        self.message = f"Invalid dataModelName '{self.data_model_name}' stored in 'Metadata' sheet, it must obey regex {self.regex_expression}!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class Error104(Error):
    name: str = "VersionRegexViolation"
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


class Warning100(UserWarning):
    name: str = "NamespaceEndingFixed"
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


class Warning101(UserWarning):
    name: str = "DataModelNameMissing"
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


class Warning102(UserWarning):
    name: str = "VersionDotsConvertedToUnderscores"
    code: int = 102
    description: str = "Version is expressed in classical form with dots major.minor.patch, while CDF accepts underscores major_minor_patch"
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


########################################
# Classes sheet Error Codes 200 - 199: #


class Error200(Error):
    name: str = "ClassIDRegexViolation"
    code: int = 200
    description: str = "Class ID, which is stored in the column 'Class' in the 'Classes' sheet, does not respect defined regex expression"
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

        self.message = f"Class id '{self.class_id}' stored in 'Class' column in 'Classes' sheet violates regex {self.regex_expression}!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class Error201(Error):
    name: str = "ClassIDMissing"
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


class Warning200(UserWarning):
    name: str = "ClassNameNotProvided"
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


class Error300(Error):
    name: str = "ClassIDRegexViolation"
    code: int = 300
    description: str = "Class ID, which is stored in the column 'Class' in the 'Properties' sheet, does not respect defined regex expression"
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

        self.message = f"Class id '{self.class_id}' stored in 'Class' column in 'Properties' sheet violates regex {self.regex_expression}!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class Error301(Error):
    name: str = "PropertyIDRegexViolation"
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

        self.message = f"Property id '{self.property_id}' stored in 'Property' column in 'Properties' sheet violates regex {self.regex_expression}!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class Error302(Error):
    name: str = "ValueTypeIDRegexViolation"
    code: int = 302
    description: str = "Value type, which is stored in the column 'Type' in the 'Properties' sheet, does not respect defined regex expression"
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

        self.message = f"Value type '{self.value_type}' stored in 'Type' column in 'Properties' sheet violates regex {self.regex_expression}!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class Error303(Error):
    name: str = "MissingTypeValue"
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


class Error304(Error):
    name: str = "PropertyIDMissing"
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


class Error305(Error):
    name: str = "CDFResourceTypeMissing"
    code: int = 305
    description: str = (
        "CDF Resource Type, which is stored in the column 'Resource Type' in the 'Properties' sheet,"
        " is either missing or did not pass validation"
    )
    example: str = ""
    fix: str = "Make sure that CDF Resource Type is provided and passes validation"

    def __init__(self, verbose=False):
        self.message = self.description
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class Error306(Error):
    name: str = "PropertyIDAndCDFResourceTypeMissing"
    code: int = 305
    description: str = (
        "Property id and CDF resource type, which are stored stored in the column 'Property'"
        " and 'Resource Type' in the 'Properties' sheet respectively,"
        " are either missing or did not pass validation"
    )
    example: str = ""
    fix: str = "Make sure that property id and CDF resource type are provided and they pass validation"

    def __init__(self, verbose=False):
        self.message = self.description
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


class Warning300(UserWarning):
    name: str = "PropertyNameNotProvided"
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


class Warning301(UserWarning):
    name: str = "MissingLabel"
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


###############################################
#  Prefixes  Error Codes 400 - 499: #


class Error400(Error):
    name: str = "PrefixesRegexViolation"
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


class Error401(Error):
    name: str = "NamespaceNotValidURL"
    code: int = 401
    description: str = "namespace(es), which are/is in the 'Prefixes' sheet, are/is not valid URLs"
    example: str = "If we have 'authority:namespace' as namespace as it is not a valid URL this error will be raised"
    fix: str = "Check if 'namespaces' in the 'Prefixes' sheet are properly constructed as valid URLs containing only allowed characters"

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


class Warning500(UserWarning):
    name: str = "MissingDataModelPrefixOrNamespace"
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


class Error600(Error):
    """Property defined for a class that has not been defined in the 'Classes' sheet"""

    name: str = "PropertyDefinedForUndefinedClass"
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


class Error601(Error):
    name: str = "MetadataSheetMissingOrFailedValidation"
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


class Error602(Error):
    name: str = "FiledInMetadataSheetMissingOrFailedValidation"
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


class Error603(Error):
    name: str = "ValueTypeNotDefinedAsClass"
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

    fix: str = "Make sure to define all of the classes in the 'Classes' sheet before defining properties that expect them as value types"

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


class Error604(Error):
    name: str = "UndefinedObjectsAsExpectedValueTypes"
    code: int = 604
    description: str = (
        "Expected value types, which are stored in the column 'Type' in the 'Properties'"
        " sheet, are classes that exist in the 'Classes' sheet but for which no properties are defined "
        "in the 'Properties' sheet. "
    )
    example: str = (
        "We have 'Class1' which has property 'edgeClass1Class2' linking it to 'Class2', thus"
        "expected value of 'edgeClass1Class2' is 'Class2'. Both 'Class1' and 'Class2' are defined in the 'Classes' sheet"
        "However, only 'Class1' has properties defined in the 'Properties' sheet, making 'Class2' an undefined object"
        " leading to this error being raised!"
    )

    fix: str = "Make sure to define properties for classes from 'Classes' sheet before defining properties that expect them as value types"

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
