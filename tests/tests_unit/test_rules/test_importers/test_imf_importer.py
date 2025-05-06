from cognite.neat.core._issues import catch_issues
from cognite.neat.core._issues.warnings._resources import ResourceRegexViolationWarning
from cognite.neat.core._rules import importers
from cognite.neat.core._rules.transformers import VerifyAnyRules
from tests.data import GraphData


def test_imf_importer():
    with catch_issues() as issues:
        read_rules = importers.IMFImporter.from_file(GraphData.imf_temp_transmitter_complete_ttl).to_rules()
        rules = VerifyAnyRules().transform(read_rules)

    regex_violations = [issue for issue in issues if isinstance(issue, ResourceRegexViolationWarning)]

    assert len(rules.classes) == 63
    assert len(rules.properties) == 62
    assert len(issues) == 207
    assert len(regex_violations) == 129
