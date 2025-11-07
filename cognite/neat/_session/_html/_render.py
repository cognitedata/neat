from typing import Any, Literal

from . import static, templates


def render(template_name: Literal["issues"], variables: dict[str, Any]) -> str:
    """Generate HTML content from a template and variables."""

    if template_name not in ["issues"]:
        raise ValueError(f"Unknown template name: {template_name}")

    variables["SHARED_CSS"] = static.shared_style.read_text()

    if template_name == "issues":
        template = templates.issues.read_text()
        variables["SCRIPTS"] = static.issues_scripts.read_text()
        variables["SPECIFIC_CSS"] = static.issues_style.read_text()

    for key, value in variables.items():
        template = template.replace(f"{{{{{key}}}}}", str(value))
    return template
