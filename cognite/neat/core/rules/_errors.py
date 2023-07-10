"""This module contains the definition of validation errors raised when parsing transformation rules.
CODES:
- 0 - 99: reserved for general errors
- 100 - 199: reserved for Metadata sheet
- 200 - 299: reserved for Prefixes sheet
- 300 - 399: reserved for Classes sheet
- 400 - 499: reserved for Properties sheet
- 500 - 599: reserved for Instances sheet
- 600 - 699: reserved for Transformation Rules, usually checking inter-sheet dependencies
"""


# Metadata sheet errors:
class Error100(Exception):
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


class Error101(Exception):
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


class Error102(Exception):
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


class Error103(Exception):
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


class Error104(Exception):
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

        self.message = f"Invalid dataModelName '{self.version}' stored in 'Metadata' sheet, it must obey regex {self.regex_expression}!"
        if verbose:
            self.message += f"\nDescription: {self.description}"
            self.message += f"\nExample: {self.example}"
            self.message += f"\nFix: {self.fix}"
        super().__init__(self.message)


# Classes sheet errors:
class Error200(Exception):
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


# Properties sheet errors:
class Error300(Exception):
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


class Error301(Exception):
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


class Error302(Exception):
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


# Transformation Rules interdependency errors:
