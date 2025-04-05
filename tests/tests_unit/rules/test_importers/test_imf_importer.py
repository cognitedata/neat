from cognite.neat._issues.warnings._resources import ResourceRegexViolationWarning
from cognite.neat._rules import importers
from cognite.neat._rules.models.information._validation import InformationValidation
from cognite.neat._rules.transformers import (
    ToCompliantEntities,
    VerifyAnyRules,
)
from cognite.neat._utils.affix import Affix
from tests.config import IMF_EXAMPLE


def test_imf_importer():
    read_rules = importers.IMFImporter.from_file(IMF_EXAMPLE).to_rules()
    rules = VerifyAnyRules().transform(read_rules)
    compliant_rules = ToCompliantEntities(Affix(prefix="IMF")).transform(rules)

    issues = InformationValidation(compliant_rules).validate()
    regex_violations = [issue for issue in issues if isinstance(issue, ResourceRegexViolationWarning)]

    assert len(issues) == 2
    assert len(regex_violations) == 0

    assert len(compliant_rules.classes) == 7
    assert any(rule.class_.suffix == "IMF_347e53f7_08f3_4e1f_9871_84b66f07a05e" for rule in compliant_rules.classes)
    assert len(compliant_rules.properties) == 75
    assert any(rule.class_.suffix == "IMF_ff48f06c_f56a_477d_a102_1a9936ab1f58" for rule in compliant_rules.classes)
