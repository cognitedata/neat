from cognite.neat._issues.warnings._resources import ResourceRegexViolationWarning
from cognite.neat._rules import importers
from cognite.neat._rules.transformers import VerifyAnyRules
from tests.config import IMF_EXAMPLE


def test_imf_importer():
    input = importers.IMFImporter.from_file(IMF_EXAMPLE).to_rules()
    output = VerifyAnyRules("continue").try_transform(input)

    regex_violations = [issue for issue in output.issues if isinstance(issue, ResourceRegexViolationWarning)]

    assert len(output.rules.classes) == 63
    assert len(output.rules.properties) == 62
    assert len(output.issues) == 207
    assert len(regex_violations) == 129
