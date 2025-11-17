from typing import Any, Literal, TypeAlias

from . import static, templates

ENCODING = "utf-8"

Template: TypeAlias = Literal["issues", "deployment"]


def render(template_name: Literal["issues", "deployment"], variables: dict[str, Any]) -> str:
    """Generate HTML content from a template and variables."""

    if template_name not in ["issues", "deployment"]:
        raise ValueError(f"Unknown template name: {template_name}")

    variables["SHARED_CSS"] = static.shared_style.read_text(encoding=ENCODING)

    if template_name == "issues":
        template = templates.issues.read_text(encoding=ENCODING)
        variables["SCRIPTS"] = static.issues_scripts.read_text(encoding=ENCODING)
        variables["SPECIFIC_CSS"] = static.issues_style.read_text(encoding=ENCODING)

    elif template_name == "deployment":
        template = templates.deployment.read_text(encoding=ENCODING)
        variables["SCRIPTS"] = static.deployment_scripts.read_text(encoding=ENCODING)
        variables["SPECIFIC_CSS"] = static.deployment_style.read_text(encoding=ENCODING)

    for key, value in variables.items():
        template = template.replace(f"{{{{{key}}}}}", str(value))
    return template
