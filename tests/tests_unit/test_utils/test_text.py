from collections.abc import Iterable

import pytest

from cognite.neat._utils.text import quote_int_value_by_key_in_yaml


def quote_key_in_yaml_test_cases() -> Iterable[tuple]:
    yield pytest.param(
        """space: my_space
externalID: myModel
version: 3_0_2""",
        '''space: my_space
externalID: myModel
version: "3_0_2"''',
        id="Single data model",
    )

    yield pytest.param(
        """- space: my_space
  externalId: myModel
  version: 1_000
- space: my_other_space
  externalId: myOtherModel
  version: 2_000
""",
        """- space: my_space
  externalId: myModel
  version: "1_000"
- space: my_other_space
  externalId: myOtherModel
  version: "2_000"
""",
        id="Two Data Models",
    )

    yield pytest.param(
        """space: my_space
externalID: myModel
version: '3_0_2'""",
        """space: my_space
externalID: myModel
version: '3_0_2'""",
        id="Single data model with single quoted version",
    )

    yield pytest.param(
        """- space: my_space
  externalId: myModel
  version: '1_000'
- space: my_other_space
  externalId: myOtherModel
  version: '2_000'
""",
        """- space: my_space
  externalId: myModel
  version: '1_000'
- space: my_other_space
  externalId: myOtherModel
  version: '2_000'
""",
        id="Two Data Models with single quoted version",
    )

    yield pytest.param(
        '''space: my_space
externalID: myModel
version: "3_0_2"''',
        '''space: my_space
externalID: myModel
version: "3_0_2"''',
        id="Single data model with double quoted version",
    )

    yield pytest.param(
        """- space: my_space
  externalId: myModel
  version: "1_000"
- space: my_other_space
  externalId: myOtherModel
  version: "2_000"
""",
        """- space: my_space
  externalId: myModel
  version: "1_000"
- space: my_other_space
  externalId: myOtherModel
  version: "2_000"
""",
        id="Two Data Models with double quoted version",
    )

    version_prop = """
externalId: CogniteSourceSystem
properties:
  version:
    container:
      externalId: CogniteSourceSystem
      space: sp_core_model
      type: container
    """
    yield pytest.param(
        version_prop,
        version_prop,
        id="Version property untouched",
    )
    yield pytest.param(
        """version: 1_0_0 # My comment""", """version: '1_0_0' # My comment""", id="Handle comment after version"
    )
    yield pytest.param(
        """version: 1 # My "quoted" comment""",
        """version: '1' # My "quoted" comment""",
        id="Handle comment with quotes after version",
    )


class TestQuoteKeyInYAML:
    @pytest.mark.parametrize("raw, expected", list(quote_key_in_yaml_test_cases()))
    def test_quote_key_in_yaml(self, raw: str, expected: str) -> None:
        assert quote_int_value_by_key_in_yaml(raw, key="version") == expected
