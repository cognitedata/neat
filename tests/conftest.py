import pytest
from pyparsing import Iterable


@pytest.fixture(scope="session")
def valid_dms_yaml_formats() -> Iterable[tuple]:
    yield pytest.param(
        """Metadata:
- Key: space
  Value: cdf_cdm
- Key: externalId
  Value: CogniteDataModel
- Key: version
  Value: v1
Properties:
- View: CogniteDescribable
  View Property: name
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: CogniteDescribable
  Container Property: name
  Index: btree:name(cursorable=True)
  Connection: null
Views:
- View: CogniteDescribable
Containers:
- Container: CogniteDescribable
  Used For: node
""",
        id="Minimal example",
    )
