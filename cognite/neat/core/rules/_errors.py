"""This module contains the definition of validation errors raised when parsing transformation rules."""


class Error100(Exception):
    code: int = 100
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


class Error101(Exception):
    code: int = 101
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


class Error102(Exception):
    code: int = 102
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


class Error103(Exception):
    code: int = 103
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


class Error104(Exception):
    code: int = 104
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


class Error105(Exception):
    code: int = 105
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
