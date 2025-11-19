"""Validators for checking if data model is AI-ready."""

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

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        if not self.local_resources.data_model_name:
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

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        if not self.local_resources.data_model_description:
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

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.local_resources.data_model_views:
            view = self.local_resources.views_by_reference.get(view_ref)

            if view is None:
                raise RuntimeError(f"View {view_ref!s} not found in local resources. This is a bug.")

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

    def run(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for view_ref in self.local_resources.data_model_views:
            view = self.local_resources.views_by_reference.get(view_ref)

            if view is None:
                raise RuntimeError(f"View {view_ref!s} not found in local resources. This is a bug.")

            if not view.description:
                recommendations.append(
                    Recommendation(
                        message=f"View {view_ref!s} is missing a description.",
                        fix="Add a clear and concise description to the view.",
                        code=self.code,
                    )
                )

        return recommendations
