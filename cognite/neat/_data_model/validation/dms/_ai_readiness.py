"""Validators for checking if data model is AI-ready."""

from cognite.neat._data_model.models.dms._data_types import EnumProperty
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import Recommendation

BASE_CODE = "NEAT-DMS-AI-READINESS"


class DataModelMissingName(DataModelValidator):
    """Validates that data model has a human-readable name.

    ## What it does
    Validates that the data model has a human-readable name.

    ## Why is this bad?
    Often the data model ids are technical identifiers, abbreviations, etc.
    A missing name makes it harder for users (humans or machines) to understand what the data model represents.
    Providing a clear name improves usability, maintainability, searchability, and AI-readiness.

    ## Example
    A data model has an id IEC61400-25-2 but no name. Users may find it difficult to understand what this data model
    represents. However adding a name "Wind Energy Information Model" would increase clarity and usability.
    """

    code = f"{BASE_CODE}-001"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        if not self.validation_resources.merged_data_model.name:
            recommendations.append(
                Recommendation(
                    message="Data model is missing a human-readable name.",
                    fix="Add a clear and concise name to the data model.",
                    code=self.code,
                )
            )

        return recommendations


class DataModelMissingDescription(DataModelValidator):
    """Validates that data model has a human-readable description.

    ## What it does
    Validates that the data model has a human-readable description.

    ## Why is this bad?
    A missing description makes it harder for users (humans or machines) to understand the purpose and scope
    of the data model. The description provides important context about what domain the data model covers,
    what use cases it supports, and how it should be used.

    ## Example
    A data model has an id CIM, with name Common Information Model, but no description. Users may find it difficult to
    understand what this data model represents, unless extra context is provided. In this particualar case, name
    does not provide sufficient information, as it is too generic, that this data model is focused on the
    electrical power systems domain. However, providing a description such as:
    "The Common Information Model (CIM) is a standard developed by IEC for representing power system
    components and their relationships. It is widely used in the electrical utility industry for data
    exchange and system modeling." would greatly improve clarity and usability.
    """

    code = f"{BASE_CODE}-002"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        if not self.validation_resources.merged_data_model.description:
            recommendations.append(
                Recommendation(
                    message="Data model is missing a description.",
                    fix="Add a clear and concise description to the data model.",
                    code=self.code,
                )
            )

        return recommendations


class ViewMissingName(DataModelValidator):
    """Validates that a View has a human-readable name.

    ## What it does
    Validates that each view in the data model has a human-readable name.

    ## Why is this bad?
    A missing name makes it harder for users (humans or machines) to understand the purpose of the view.
    This is important as views' external ids are often based on technical identifiers, abbreviations, etc.
    Providing a clear name improves usability, maintainability, searchability, and AI-readiness.

    ## Example
    A view has an id CFIHOS-30000038 but no name. Users may find it difficult to understand what this view represents,
    unless they look up the id in documentation or other resources. Adding name "Pump" would increase clarity and
    usability.
    """

    code = f"{BASE_CODE}-003"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.validation_resources.merged_data_model.views or []:
            view = self.validation_resources.select_view(view_ref)

            if view is None:
                raise RuntimeError(f"{type(self).__name__}: View {view_ref!s} not found. This is a bug.")

            if not view.name:
                recommendations.append(
                    Recommendation(
                        message=f"View {view_ref!s} is missing a human-readable name.",
                        fix="Add a clear and concise name to the view.",
                        code=self.code,
                    )
                )

        return recommendations


class ViewMissingDescription(DataModelValidator):
    """Validates that a View has a human-readable description.

    ## What it does
    Validates that each view in the data model has a human-readable description.

    ## Why is this bad?
    A missing description makes it harder for users (humans or machines) to understand in what context the view
    should be used. The description can provide important information about the view's purpose, scope, and usage.


    ## Example
    A view Site has no description. Users may find it difficult to understand what this view represents, unless
    extra context is provided. Even if we know that Site is used in the context of wind energy developments, a
    description is necessary as it can be used in various context within the same domain such as:

    Option 1 — Project area
    This view represents a geographical area where wind energy projects are developed and managed.

    Option 2 — Lease area
    The legally defined lease area allocated for offshore wind development.

    Option 3 — Measurement site
    A specific location where wind measurements (e.g., LiDAR, met mast) are collected.

    """

    code = f"{BASE_CODE}-004"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.validation_resources.merged_data_model.views or []:
            view = self.validation_resources.select_view(view_ref)

            if view is None:
                raise RuntimeError(f"{type(self).__name__}: View {view_ref!s} not found. This is a bug.")

            if not view.description:
                recommendations.append(
                    Recommendation(
                        message=f"View {view_ref!s} is missing a description.",
                        fix="Add a clear and concise description to the view.",
                        code=self.code,
                    )
                )

        return recommendations


class ViewPropertyMissingName(DataModelValidator):
    """Validates that a view property has a human-readable name.

    ## What it does
    Validates that each view property in the data model has a human-readable name.

    ## Why is this bad?
    A missing name makes it harder for users (humans or machines) to understand the purpose of the view property.
    This is important as view property's ids are often based on technical identifiers, abbreviations, etc.
    Providing a clear name improves usability, maintainability, searchability, and AI-readiness.

    ## Example
    A view WindTurbine has a property pc which has no name. Users may find it difficult to understand what this view
    property represents, unless they look up the id in documentation or other resources. Adding name "power curve"
    would increase clarity and usability.
    """

    code = f"{BASE_CODE}-005"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.validation_resources.merged_data_model.views or []:
            view = self.validation_resources.select_view(view_ref)

            if view is None:
                raise RuntimeError(f"{type(self).__name__}: View {view_ref!s} not found. This is a bug.")

            if not view.properties:
                continue

            for prop_ref, definition in view.properties.items():
                if not definition.name:
                    recommendations.append(
                        Recommendation(
                            message=f"View {view_ref!s} property {prop_ref!s} is missing a human-readable name.",
                            fix="Add a clear and concise name to the view property.",
                            code=self.code,
                        )
                    )

        return recommendations


class ViewPropertyMissingDescription(DataModelValidator):
    """Validates that a View property has a human-readable description.

    ## What it does
    Validates that each view property in the data model has a human-readable description.

    ## Why is this bad?
    A missing description makes it harder for users (humans or machines) to understand in what context the view property
    should be used. The description can provide important information about the view property's purpose,
    scope, and usage.


    ## Example
    A view WindTurbine has a property status with no description. Users may find it difficult to understand what this
    property represents, unless extra context is provided. Even if we know that status is related to wind turbine
    operations, a description is necessary as it can have different meanings in various contexts:

    Option 1 — Operational status
    Current operational state of the wind turbine (e.g., running, stopped, maintenance, fault).

    Option 2 — Connection status
    Grid connection status indicating whether the turbine is connected to the electrical grid.

    Option 3 — Availability status
    Availability state for production indicating whether the turbine is available for power generation.

    """

    code = f"{BASE_CODE}-006"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.validation_resources.merged_data_model.views or []:
            view = self.validation_resources.select_view(view_ref)

            if view is None:
                raise RuntimeError(f"{type(self).__name__}: View {view_ref!s} not found. This is a bug.")

            if not view.properties:
                continue

            for prop_ref, definition in view.properties.items():
                if not definition.description:
                    recommendations.append(
                        Recommendation(
                            message=f"View {view_ref!s} property {prop_ref!s} is missing a description.",
                            fix="Add a clear and concise description to the view property.",
                            code=self.code,
                        )
                    )

        return recommendations


class EnumerationMissingName(DataModelValidator):
    """Validates that an enumeration has a human-readable name.

    ## What it does
    Validates that each enumeration value in the data model has a human-readable name.

    ## Why is this bad?
    A missing name makes it harder for users (humans or machines) to understand the purpose of the enumeration value.
    This is important as enumeration values are often technical codes or abbreviations, and a clear name improves
    usability, maintainability, searchability, and AI-readiness.

    ## Example
    An enumeration value with id "NOM" in a wind turbine operational mode property has no name. Users may find it
    difficult to understand what this value represents. Adding name "Normal Operation" would increase clarity
    and usability.
    """

    code = f"{BASE_CODE}-007"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for container_ref in self.validation_resources.merged.containers:
            container = self.validation_resources.select_container(container_ref)

            if not container:
                raise RuntimeError(f"{type(self).__name__}: Container {container_ref!s} not found. This is a bug.")

            for prop_ref, definition in container.properties.items():
                if not isinstance(definition.type, EnumProperty):
                    continue

                for value, enum_def in definition.type.values.items():
                    if not enum_def.name:
                        recommendations.append(
                            Recommendation(
                                message=(
                                    f"Enumeration value {value!r} in property {prop_ref!s} of container "
                                    f"{container_ref!s} is missing a human-readable name."
                                ),
                                fix="Add a clear and concise name to the enumeration value.",
                                code=self.code,
                            )
                        )

        return recommendations


class EnumerationMissingDescription(DataModelValidator):
    """Validates that an enumeration value has a human-readable description.

    ## What it does
    Validates that each enumeration value in the data model has a human-readable description.

    ## Why is this bad?
    A missing description makes it harder for users (humans or machines) to understand the meaning and context
    of the enumeration value. The description can provide important information about when and how the value
    should be used, especially when enumeration values are technical codes or abbreviations.

    ## Example
    An enumeration value "NOM" in a wind turbine operational mode property has no description. Users may find it
    difficult to understand what this value represents without additional context. Even with a name like
    "Normal Operation", the description is valuable as it can clarify specifics:

    Option 1 — Basic definition
    The turbine is operating normally and generating power according to its power curve.

    Option 2 — Detailed operational context
    The turbine is in normal operation mode, actively generating power with all systems functioning within
    specified parameters and connected to the grid.

    Option 3 — Contrasting with other modes
    Standard operating mode where the turbine follows the power curve and responds to grid commands,
    as opposed to maintenance mode or fault conditions.
    """

    code = f"{BASE_CODE}-008"
    issue_type = Recommendation

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for container_ref in self.validation_resources.merged.containers:
            container = self.validation_resources.select_container(container_ref)
            if not container:
                raise RuntimeError(f"{self.__class__.__name__}: Container {container_ref!s} not found. This is a bug.")

            for prop_ref, definition in container.properties.items():
                if not isinstance(definition.type, EnumProperty):
                    continue

                for value, enum_def in definition.type.values.items():
                    if not enum_def.description:
                        recommendations.append(
                            Recommendation(
                                message=(
                                    f"Enumeration value {value!r} in property {prop_ref!s} of container "
                                    f"{container_ref!s} is missing a human-readable description."
                                ),
                                fix="Add a clear and concise description to the enumeration value.",
                                code=self.code,
                            )
                        )

        return recommendations
