from cognite.neat.core._data_model import importers
from cognite.neat.core._data_model.transformers import VerifyAnyDataModel
from cognite.neat.core._issues import catch_issues
from cognite.neat.core._issues.warnings._resources import ResourceRegexViolationWarning
from tests.data import GraphData


def test_imf_importer():
    with catch_issues() as issues:
        read_rules = importers.IMFImporter.from_file(GraphData.imf_temp_transmitter_complete_ttl).to_data_model()
        rules = VerifyAnyDataModel().transform(read_rules)

    regex_violations = [issue for issue in issues if isinstance(issue, ResourceRegexViolationWarning)]

    assert len(rules.concepts) == 63
    assert len(rules.properties) == 62
    assert len(issues) == 207
    assert len(regex_violations) == 129
