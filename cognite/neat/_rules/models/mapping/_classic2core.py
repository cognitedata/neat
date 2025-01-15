from functools import lru_cache
from pathlib import Path

import yaml

from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.models.dms import DMSInputRules, DMSRules

_CLASSIC_TO_CORE_MAPPING = Path(__file__).resolve().parent / "_classic2core.yaml"


@lru_cache(maxsize=1)
def _read_source_file() -> str:
    return _CLASSIC_TO_CORE_MAPPING.read_text()


def load_classic_to_core_mapping(org_name: str | None, source_space: str, source_version: str) -> DMSRules:
    from cognite.neat._rules.importers import YAMLImporter
    from cognite.neat._rules.transformers import VerifyDMSRules

    raw_str = _read_source_file()
    if org_name is not None:
        raw_str = raw_str.replace("Classic", org_name)

    loaded = yaml.safe_load(raw_str)
    loaded["metadata"]["space"] = source_space
    loaded["metadata"]["version"] = source_version

    read: ReadRules[DMSInputRules] = YAMLImporter(loaded).to_rules()
    if not isinstance(read.rules, DMSInputRules):
        raise NeatValueError(f"Expected DMS rules, but got {type(read.rules).__name__}")

    verified = VerifyDMSRules(validate=False).transform(read)

    return verified
